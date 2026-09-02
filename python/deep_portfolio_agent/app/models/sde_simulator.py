import jax
import jax.numpy as jnp

class SDESimulator:
    def __init__(self, num_assets: int, num_simulations: int, num_steps: int = 21):
        """
        :param num_assets: Số lượng tài sản (VD: 100)
        :param num_simulations: Số kịch bản Monte Carlo (VD: 10,000)
        :param num_steps: Số bước thời gian mô phỏng (VD: 21 ngày = 1 tháng giao dịch)
        """
        self.num_assets = num_assets
        self.num_simulations = num_simulations
        self.num_steps = num_steps

    @jax.jit
    def simulate_gbm(self, key, S0, mean_returns, cov_matrix):
        """
        Mô phỏng Geometric Brownian Motion cho đa tài sản bằng JAX.
        :param S0: Giá hiện tại của tài sản, shape (num_assets,)
        :param mean_returns: Vector lợi nhuận kỳ vọng, shape (num_assets,)
        :param cov_matrix: Ma trận hiệp phương sai, shape (num_assets, num_assets)
        :return: Mảng quỹ đạo giá, shape (num_simulations, num_steps, num_assets)
        """
        # Phân rã Cholesky để lấy ma trận tam giác dưới L (tương quan)
        # Thêm một chút nhiễu vào đường chéo chính để đảm bảo ma trận dương xác định (Numerical Stability)
        eps = 1e-8
        cov_matrix_stable = cov_matrix + jnp.eye(self.num_assets) * eps
        L = jnp.linalg.cholesky(cov_matrix_stable)
        
        # Phương sai (đường chéo của cov_matrix)
        variances = jnp.diag(cov_matrix)
        
        # Drift = mu - 0.5 * sigma^2
        drift = mean_returns - 0.5 * variances
        
        # Tạo số ngẫu nhiên chuẩn chuẩn tắc cho tất cả các bước và kịch bản
        # Shape: (num_simulations, num_steps - 1, num_assets)
        Z = jax.random.normal(key, shape=(self.num_simulations, self.num_steps - 1, self.num_assets))
        
        # Biến đổi Z thành Z_corr có tính đến tương quan: Z_corr = Z * L^T
        # jnp.einsum để nhân ma trận hàng loạt
        Z_corr = jnp.einsum('sta,ba->stb', Z, L)
        
        # Tính toán log return từng bước
        step_returns = drift + Z_corr
        
        # Cấu trúc mảng giá: Khởi tạo với 0
        log_S = jnp.zeros((self.num_simulations, self.num_steps, self.num_assets))
        
        # Đặt giá trị ban đầu là log(S0)
        log_S = log_S.at[:, 0, :].set(jnp.log(S0))
        
        # Cộng dồn lợi nhuận (cumulative sum dọc theo trục thời gian)
        cumulative_returns = jnp.cumsum(step_returns, axis=1)
        log_S = log_S.at[:, 1:, :].add(cumulative_returns)
        
        # Chuyển từ log price sang price
        S = jnp.exp(log_S)
        return S
