"""
Kiểm chứng LegendreChaos.

Chạy bằng Numpy thuần nên không cần JAX (JAX chưa cài trong môi trường này).
Hàm đáp ứng ở test cuối mô phỏng lại đúng logic của `sde_simulator.simulate_gbm`
+ `risk_manager.calculate_var_es`; khi chạy thật chỉ cần thay bằng hàm JAX.

    python -m pytest test_pce_uncertainty.py     (hoặc)     python test_pce_uncertainty.py
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app.models.pce_uncertainty import LegendreChaos, UncertainParam


def test_reproduces_polynomial_exactly():
    """Đáp ứng là đa thức bậc <= order thì PCE phải tái tạo chính xác tới sai số máy."""
    p = [UncertainParam("a", -2.0, 4.0), UncertainParam("b", 0.0, 1.0)]
    za = lambda a: 2 * (a - (-2.0)) / 6.0 - 1.0
    zb = lambda b: 2 * b - 1.0
    f = lambda a, b: 1.0 + 2 * za(a) - 3 * za(a) ** 2 + 0.5 * za(a) * zb(b) ** 3

    pce = LegendreChaos(p, order=3).fit(f)
    rng = np.random.default_rng(0)
    for _ in range(50):
        a, b = rng.uniform(-2, 4), rng.uniform(0, 1)
        assert abs(pce.predict(a=a, b=b) - f(a, b)) < 1e-12
    print("  ✓ tái tạo đa thức chính xác (sai số < 1e-12)")


def test_moments_match_analytic():
    """E, Var và Sobol khớp công thức giải tích cho f = A*z1 + B*z2 + C*z1*z2."""
    A, B, C = 3.0, -1.5, 0.75
    p = [UncertainParam("x", -1.0, 1.0), UncertainParam("y", -1.0, 1.0)]
    f = lambda x, y: A * x + B * y + C * x * y

    pce = LegendreChaos(p, order=2).fit(f)

    # ⟨P_1²⟩ = 1/3 dưới prior đều trên [-1,1]
    var_true = A**2 / 3 + B**2 / 3 + C**2 / 9
    assert abs(pce.mean - 0.0) < 1e-12, pce.mean
    assert abs(pce.variance - var_true) < 1e-12, (pce.variance, var_true)

    s1 = pce.sobol_first()
    st = pce.sobol_total()
    assert abs(s1["x"] - (A**2 / 3) / var_true) < 1e-12
    assert abs(s1["y"] - (B**2 / 3) / var_true) < 1e-12
    assert abs(st["x"] - (A**2 / 3 + C**2 / 9) / var_true) < 1e-12
    assert abs(st["x"] - s1["x"] - (C**2 / 9) / var_true) < 1e-12   # phần tương tác
    print(f"  ✓ E={pce.mean:.1e}  Var={pce.variance:.6f} (giải tích {var_true:.6f})")
    print(f"  ✓ Sobol bậc 1: x={s1['x']:.4f}  y={s1['y']:.4f}   tổng: x={st['x']:.4f}")


def test_vector_valued_response():
    """Đáp ứng dạng vector (VD trả về cả VaR lẫn ES, hoặc cả vector tỷ trọng)."""
    p = [UncertainParam("m", 0.5, 1.5)]
    f = lambda m: np.array([m, m**2, -m])

    pce = LegendreChaos(p, order=2).fit(f)
    assert pce.coeffs.shape == (3, 3)
    got = pce.predict(m=1.2)
    assert got.shape == (3,)
    assert np.allclose(got, [1.2, 1.44, -1.2], atol=1e-12)
    # m ~ U(0.5, 1.5): E[m]=1, E[m²]=Var+E[m]²=1/12+1, E[-m]=-1
    assert np.allclose(pce.mean, [1.0, 1 + 1 / 12, -1.0], atol=1e-12), pce.mean
    print(f"  ✓ đáp ứng vector shape={pce.response_shape}, predict={got}")


def test_budget_accounting():
    p = [UncertainParam("a", 0, 1), UncertainParam("b", 0, 1), UncertainParam("c", 0, 1)]
    pce = LegendreChaos(p, order=3)
    assert pce.num_evaluations == 4**3 == len(pce.design_points())
    assert set(pce.design_points()[0]) == {"a", "b", "c"}
    print(f"  ✓ ngân sách mô phỏng: {pce.num_evaluations} lần chạy cho 3 tham số, order=3")


def test_against_dense_grid_on_real_pipeline():
    """So PCE với lưới dày trên đúng pipeline GBM -> VaR của agent."""
    NA, NSIM, STEPS, ALPHA = 20, 4000, 21, 0.05
    rng = np.random.default_rng(11)
    base_mu = rng.normal(0.0004, 0.0004, NA)
    A = rng.standard_normal((NA, NA)) / np.sqrt(NA)
    base_cov = A @ A.T * 0.0004 + np.eye(NA) * 0.0002
    weights = np.ones(NA) / NA
    chol = np.linalg.cholesky(base_cov)

    # Common random numbers: BẮT BUỘC dùng chung một khối nhiễu cho mọi bộ tham số
    Z = np.random.default_rng(99).standard_normal((NSIM, STEPS, NA))

    def var95(drift_mult, vol_mult):
        drift = drift_mult * base_mu - 0.5 * (vol_mult**2) * np.diag(base_cov)
        log_s = (drift + vol_mult * np.einsum("sta,ba->stb", Z, chol)).sum(axis=1)
        returns = (np.exp(log_s) - 1.0) @ weights
        return np.percentile(returns, ALPHA * 100)

    params = [UncertainParam("drift_mult", 0.2, 1.8), UncertainParam("vol_mult", 0.5, 1.5)]

    t0 = time.perf_counter()
    pce = LegendreChaos(params, order=2).fit(var95)      # 3x3 = 9 lần chạy MC
    t_pce = time.perf_counter() - t0

    g = 21
    t0 = time.perf_counter()
    dm = np.linspace(0.2, 1.8, g)
    vm = np.linspace(0.5, 1.5, g)
    ref = np.array([[var95(a, b) for b in vm] for a in dm])
    t_ref = time.perf_counter() - t0

    sur = np.array([[pce.predict(drift_mult=a, vol_mult=b) for b in vm] for a in dm])
    max_err = np.abs(sur - ref).max()
    span = ref.max() - ref.min()

    ref_mean = np.trapezoid(np.trapezoid(ref, vm, axis=1), dm) / ((1.8 - 0.2) * (1.5 - 0.5))
    ref_std = np.sqrt(
        np.trapezoid(np.trapezoid((ref - ref_mean) ** 2, vm, axis=1), dm) / ((1.8 - 0.2) * (1.5 - 0.5))
    )

    print(f"  lưới dày   : {g*g:4d} lần chạy MC, {t_ref:5.1f}s  E[VaR]={ref_mean:.6f} Std={ref_std:.6f}")
    print(f"  PCE order=2: {pce.num_evaluations:4d} lần chạy MC, {t_pce:5.1f}s  "
          f"E[VaR]={float(pce.mean):.6f} Std={float(pce.std):.6f}")
    print(f"  sai số mặt đáp ứng: {max_err:.2e} trên dải VaR rộng {span:.2e} "
          f"({100*max_err/span:.2f}%)   tăng tốc {t_ref/t_pce:.0f}x")

    assert max_err / span < 0.02, f"mặt đáp ứng lệch {100*max_err/span:.2f}%"
    assert abs(float(pce.mean) - ref_mean) / abs(ref_mean) < 0.01
    assert abs(float(pce.std) - ref_std) / ref_std < 0.05

    s = pce.sobol_first()
    print(f"  Sobol bậc 1: drift={float(s['drift_mult']):.3f}  vol={float(s['vol_mult']):.3f}")


if __name__ == "__main__":
    for fn in (test_reproduces_polynomial_exactly, test_moments_match_analytic,
               test_vector_valued_response, test_budget_accounting,
               test_against_dense_grid_on_real_pipeline):
        print(f"\n[{fn.__name__}]")
        fn()
    print("\nTất cả kiểm chứng PASS.")
