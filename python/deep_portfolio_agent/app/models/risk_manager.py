import jax.numpy as jnp
import numpy as np

class RiskManager:
    """
    Module quản trị rủi ro. Tính toán các chỉ số rủi ro dựa trên quỹ đạo Monte Carlo.
    """
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level

    def calculate_var_es(self, target_weights, S_trajectories):
        """
        Tính Value at Risk (VaR) và Expected Shortfall (ES)
        
        :param target_weights: Tỷ trọng phân bổ vốn, shape (num_assets,)
        :param S_trajectories: Quỹ đạo giá từ Monte Carlo, shape (num_simulations, num_steps, num_assets)
        :return: (VaR, ES) dưới dạng phần trăm (VD: -0.05 nghĩa là lỗ 5%)
        """
        # Trạng thái hiện tại (bước t=0)
        S0 = S_trajectories[:, 0, :]
        
        # Trạng thái tương lai (bước t=T cuối cùng của mô phỏng)
        ST = S_trajectories[:, -1, :]
        
        # Lợi nhuận của từng tài sản (Return)
        asset_returns = (ST - S0) / S0
        
        # Lợi nhuận của toàn bộ danh mục cho mỗi kịch bản
        # Sum(w_i * R_i)
        portfolio_returns = jnp.sum(target_weights * asset_returns, axis=-1)
        
        # Tính Percentile cho VaR (Vd: confidence=0.95 -> lấy bách phân vị thứ 5)
        alpha = 1.0 - self.confidence_level
        # Chuyển sang numpy để dùng percentile vì JAX đôi khi có hạn chế với percentile
        port_returns_np = np.array(portfolio_returns)
        
        var = np.percentile(port_returns_np, alpha * 100)
        
        # Expected Shortfall: Trung bình của các khoản lỗ vượt quá VaR
        tail_losses = port_returns_np[port_returns_np <= var]
        es = np.mean(tail_losses) if len(tail_losses) > 0 else var
        
        return float(var), float(es)

    def assess_risk(self, var: float, es: float, var_threshold: float = -0.15):
        """
        Đánh giá xem rủi ro có vượt ngưỡng chịu đựng không.
        :param var_threshold: Ngưỡng VaR tối đa cho phép (VD: -0.15 = rủi ro lỗ 15% vốn)
        """
        if var < var_threshold:
            return True, "CẢNH BÁO ĐỎ: Rủi ro VaR vượt ngưỡng an toàn. Khuyến nghị Bán Hạ Tỷ Trọng / Tăng Tiền Mặt!"
        return False, "Danh mục đang ở trạng thái an toàn."
