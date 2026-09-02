import jax
import jax.numpy as jnp
import flax.linen as nn
import optax
from typing import Sequence

class PortfolioPolicyNet(nn.Module):
    """
    Mạng Nơ-ron đóng vai trò như một Policy để phân bổ vốn.
    Đầu vào: Trạng thái hiện tại của thị trường (VD: Giá các tài sản).
    Đầu ra: Tỷ trọng phân bổ vốn cho các tài sản (tổng = 1).
    """
    num_assets: int
    features: Sequence[int] = (64, 64)

    @nn.compact
    def __call__(self, x):
        for feat in self.features:
            x = nn.Dense(feat)(x)
            x = nn.relu(x)
        # Layer cuối trả về vector có số chiều = số tài sản
        logits = nn.Dense(self.num_assets)(x)
        # Softmax để đảm bảo tổng tỷ trọng = 1 và không có vị thế bán khống (Long-only)
        # Nếu cho phép bán khống (Short-selling), có thể dùng hàm kích hoạt khác như Tanh
        weights = jax.nn.softmax(logits, axis=-1)
        return weights

class NeuralPDEOptimizer:
    def __init__(self, num_assets: int, learning_rate: float = 1e-3):
        self.num_assets = num_assets
        self.model = PortfolioPolicyNet(num_assets=num_assets)
        self.optimizer = optax.adam(learning_rate)

    def init_params(self, key, input_shape):
        """Khởi tạo trọng số cho mạng Nơ-ron."""
        dummy_x = jnp.ones(input_shape)
        params = self.model.init(key, dummy_x)
        opt_state = self.optimizer.init(params)
        return params, opt_state

    @staticmethod
    def loss_fn(params, model, S_trajectories):
        """
        Hàm loss function. 
        Mục tiêu (để tối thiểu hóa): Âm lợi nhuận hoặc Phạt rủi ro (Negative Utility).
        Ở đây dùng một phiên bản đơn giản: Tối đa hóa lợi nhuận Sharpe Ratio (tối thiểu hóa -Sharpe).
        
        :param S_trajectories: (num_simulations, num_steps, num_assets)
        """
        # Trạng thái hiện tại (bước t=0)
        S0 = S_trajectories[:, 0, :]
        
        # Mạng nơ-ron tính toán tỷ trọng w từ S0
        w = model.apply(params, S0) # shape (num_simulations, num_assets)
        
        # Tính toán lợi nhuận tại bước T (cuối cùng)
        ST = S_trajectories[:, -1, :]
        # Tỷ suất sinh lời của từng tài sản từ t=0 đến t=T
        R = (ST - S0) / S0
        
        # Lợi nhuận của danh mục cho từng kịch bản (w * R)
        portfolio_returns = jnp.sum(w * R, axis=-1)
        
        # Tính Sharpe Ratio: Mean(returns) / Std(returns)
        mean_return = jnp.mean(portfolio_returns)
        std_return = jnp.std(portfolio_returns)
        
        # Phạt nếu std = 0 để tránh lỗi chia 0
        sharpe_ratio = mean_return / (std_return + 1e-6)
        
        # Mục tiêu là tối đa hóa Sharpe -> tối thiểu hóa âm Sharpe
        return -sharpe_ratio

    @jax.jit
    def train_step(self, params, opt_state, S_trajectories):
        """Một bước cập nhật trọng số mạng Nơ-ron bằng Gradient Descent."""
        loss, grads = jax.value_and_grad(self.loss_fn)(params, self.model, S_trajectories)
        updates, new_opt_state = self.optimizer.update(grads, opt_state, params)
        new_params = optax.apply_updates(params, updates)
        return loss, new_params, new_opt_state
