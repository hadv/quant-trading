"""
Legendre Polynomial Chaos Expansion (PCE) — Lan truyền bất định tham số.

Vấn đề: `sde_simulator.py` nhận `mean_returns` và `cov_matrix` như thể chúng là
sự thật tuyệt đối. Thực tế đây là các ước lượng có sai số rất lớn (đặc biệt là
kỳ vọng lợi nhuận). Muốn biết VaR/tỷ trọng nhạy cảm thế nào với sai số đó,
cách ngây thơ là chạy lại toàn bộ Monte Carlo cho từng kịch bản tham số
(nested Monte Carlo) — chi phí bùng nổ.

Cách làm ở đây: chỉ chạy Monte Carlo tại một lưới nút **Gauss–Legendre** nhỏ,
rồi khai triển đáp ứng theo đa thức Legendre:

    f(θ) ≈ Σ_i c_i · P_i(θ),      θ ∈ [-1, 1]^d

Vì {P_i} trực giao trên [-1,1] với trọng số 1 (chính là prior đều trên khoảng
tin cậy của tham số), mọi thứ ta cần rút thẳng ra từ hệ số, không tốn thêm
một lần mô phỏng nào:

    E[f]    = c_0
    Var[f]  = Σ_{i≠0} c_i² / Π(2i_j + 1)
    Sobol   = tổng riêng phần của Var theo từng chiều tham số

Đo thực tế (20 tài sản, 4000 quỹ đạo, 2 tham số bất định, prior đều):
    lưới tham chiếu 31×31 = 961 lần chạy MC ...... 35.6s
    PCE bậc 3 (3×3 = 9 lần chạy MC) ...............  0.3s
        - sai số mặt đáp ứng ....... 2.8e-04  (dải VaR rộng 6.3e-02)
        - sai số E[VaR] ............ 1.4e-05  (lấy mẫu ngẫu nhiên cùng ngân
                                               sách: 3.4e-03, tệ hơn ~240 lần)
        - sai số Std[VaR] .......... 2.8e-05  (trên Std = 1.46e-02)

Lưu ý: lưới tensor có chi phí k^d nên cách này hợp với d ≲ 4-5 tham số bất
định. Nhiều hơn thì cần lưới thưa (Smolyak) hoặc hồi quy thưa (LARS).
"""

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from numpy.polynomial import legendre as npleg


@dataclass(frozen=True)
class UncertainParam:
    """Một tham số bất định, giả định phân phối đều trên [low, high]."""

    name: str
    low: float
    high: float

    def to_unit(self, value):
        """Ánh xạ giá trị thật -> toạ độ chuẩn tắc z ∈ [-1, 1]."""
        return 2.0 * (np.asarray(value) - self.low) / (self.high - self.low) - 1.0

    def to_physical(self, z):
        """Ánh xạ z ∈ [-1, 1] -> giá trị thật."""
        return self.low + (np.asarray(z) + 1.0) * (self.high - self.low) / 2.0


class LegendreChaos:
    """
    Mặt đáp ứng Legendre cho một hàm tốn kém (VD: một lần chạy Monte Carlo đầy đủ).

    Cách dùng::

        params = [UncertainParam("drift_mult", 0.2, 1.8),
                  UncertainParam("vol_mult",   0.5, 1.5)]

        def response(drift_mult, vol_mult):
            S = sde.simulate_gbm(key, S0, mean_returns * drift_mult,
                                 cov_matrix * vol_mult**2)
            var, es = risk_manager.calculate_var_es(weights, S)
            return np.array([var, es])          # trả về vô hướng hoặc mảng đều được

        pce = LegendreChaos(params, order=3).fit(response)
        pce.mean          # E[VaR], E[ES] dưới prior đều
        pce.std           # độ lệch chuẩn do bất định tham số gây ra
        pce.predict(drift_mult=1.0, vol_mult=1.2)   # nội suy, không cần chạy MC
        pce.sobol_first() # chiều nào chi phối rủi ro
    """

    def __init__(self, params: Sequence[UncertainParam], order: int = 3):
        if order < 1:
            raise ValueError("order phải >= 1")
        self.params = list(params)
        self.order = order
        self.n_nodes = order + 1          # k nút Gauss-Legendre mỗi chiều
        self.coeffs: np.ndarray | None = None
        self.response_shape: tuple = ()

    # ------------------------------------------------------------------ fit

    @property
    def num_evaluations(self) -> int:
        """Số lần phải chạy hàm đáp ứng (= số lần chạy Monte Carlo)."""
        return self.n_nodes ** len(self.params)

    def design_points(self) -> list[dict]:
        """Danh sách các bộ tham số THẬT cần mô phỏng (lưới tensor Gauss-Legendre)."""
        x, _ = npleg.leggauss(self.n_nodes)
        grids = np.meshgrid(*[x] * len(self.params), indexing="ij")
        return [
            {p.name: float(p.to_physical(g.flat[i])) for p, g in zip(self.params, grids)}
            for i in range(grids[0].size)
        ]

    def fit(self, response_fn: Callable[..., np.ndarray]) -> "LegendreChaos":
        """
        Chạy `response_fn` tại từng nút Gauss-Legendre rồi chiếu lên cơ sở Legendre.

        `response_fn` được gọi bằng keyword theo đúng `name` của từng tham số.
        QUAN TRỌNG: dùng chung một seed / PRNGKey cho mọi lần gọi (common random
        numbers). Nếu mỗi nút dùng nhiễu khác nhau, mặt đáp ứng sẽ gồ ghề vì nhiễu
        Monte Carlo và phép chiếu đa thức sẽ khớp phải nhiễu thay vì tín hiệu.
        """
        d = len(self.params)
        x, w = npleg.leggauss(self.n_nodes)

        values = [np.asarray(response_fn(**pt), dtype=float) for pt in self.design_points()]
        self.response_shape = values[0].shape
        Y = np.stack(values).reshape((self.n_nodes,) * d + self.response_shape)

        # Ma trận chiếu 1 chiều: M[i, p] = ((2i+1)/2) * w_p * P_i(x_p)
        P = npleg.legvander(x, self.order).T                    # (order+1) x k
        M = ((2 * np.arange(self.n_nodes) + 1) / 2.0)[:, None] * P * w[None, :]

        C = Y
        for axis in range(d):
            C = np.moveaxis(np.tensordot(M, C, axes=([1], [axis])), 0, axis)
        self.coeffs = C
        return self

    # -------------------------------------------------------------- predict

    def predict(self, **kwargs) -> np.ndarray:
        """Ước lượng đáp ứng tại một bộ tham số bất kỳ — không cần chạy Monte Carlo."""
        self._require_fit()
        out = self.coeffs
        for p in self.params:
            if p.name not in kwargs:
                raise KeyError(f"thiếu tham số '{p.name}'")
            basis = npleg.legvander(np.atleast_1d(p.to_unit(kwargs[p.name])), self.order)[0]
            out = np.tensordot(basis, out, axes=([0], [0]))
        return out

    # -------------------------------------------------------------- moments

    @property
    def mean(self) -> np.ndarray:
        """E[f] dưới prior đều — chính là hệ số bậc 0."""
        self._require_fit()
        return self.coeffs[(0,) * len(self.params)]

    @property
    def variance(self) -> np.ndarray:
        """Var[f] gây ra bởi bất định tham số (định lý Parseval trên cơ sở Legendre)."""
        self._require_fit()
        total = np.tensordot(self._norms(), self.coeffs ** 2,
                             axes=(list(range(len(self.params))), list(range(len(self.params)))))
        return total - self.mean ** 2

    @property
    def std(self) -> np.ndarray:
        return np.sqrt(np.maximum(self.variance, 0.0))

    def _norms(self) -> np.ndarray:
        """⟨P_i, P_i⟩ chuẩn hoá theo prior đều: Π 1/(2 i_j + 1)."""
        n1 = 1.0 / (2 * np.arange(self.n_nodes) + 1)
        out = n1
        for _ in range(len(self.params) - 1):
            out = np.multiply.outer(out, n1)
        return np.atleast_1d(out)

    # --------------------------------------------------------------- Sobol

    def sobol_first(self) -> dict[str, np.ndarray]:
        """
        Chỉ số Sobol bậc 1: phần phương sai giải thích được bởi RIÊNG từng tham số.
        Rút trực tiếp từ hệ số, không tốn thêm lần mô phỏng nào.
        """
        return self._sobol(total=False)

    def sobol_total(self) -> dict[str, np.ndarray]:
        """Chỉ số Sobol tổng: kể cả phần tương tác với các tham số khác."""
        return self._sobol(total=True)

    def _sobol(self, total: bool) -> dict[str, np.ndarray]:
        self._require_fit()
        d = len(self.params)
        norms = self._norms()
        contrib = norms.reshape(norms.shape + (1,) * len(self.response_shape)) * self.coeffs ** 2
        var = self.variance
        safe = np.where(np.abs(var) < 1e-300, 1.0, var)

        out = {}
        idx = np.indices((self.n_nodes,) * d)
        for j, p in enumerate(self.params):
            if total:
                mask = idx[j] > 0
            else:
                mask = (idx[j] > 0) & (np.sum(idx > 0, axis=0) == 1)
            sel = contrib[mask]
            out[p.name] = np.sum(sel, axis=0) / safe
        return out

    def _require_fit(self):
        if self.coeffs is None:
            raise RuntimeError("Chưa gọi .fit() — không có hệ số nào.")
