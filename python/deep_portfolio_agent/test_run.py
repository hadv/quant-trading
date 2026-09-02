import sys
import os
import matplotlib.pyplot as plt

# Thêm đường dẫn để import từ app
sys.path.append('/Users/hadv/quant-trading/python/deep_portfolio_agent')

import jax
import jax.numpy as jnp
from app.data_loader import DataLoader
from app.config import config
from app.models.sde_simulator import SDESimulator
from app.models.neural_solver import NeuralPDEOptimizer

def run_test():
    print("Starting Test Run for JAX Deep Portfolio Agent...")
    loader = DataLoader()
    
    assets = loader.load_top_100_assets()
    df_prices = loader.load_historical_candles(assets)
    mean_returns, cov_matrix = loader.calculate_returns_and_covariance(df_prices)
    
    num_assets = len(assets)
    num_simulations = config.NUM_SIMULATIONS
    
    sde = SDESimulator(num_assets=num_assets, num_simulations=num_simulations, num_steps=21)
    rng_key = jax.random.PRNGKey(42)
    rng_key, subkey = jax.random.split(rng_key)
    
    S0_array = jnp.ones(num_assets) * 100.0
    
    print("Simulating...")
    S_trajectories = sde.simulate_gbm(subkey, S0_array, jnp.array(mean_returns), jnp.array(cov_matrix))
    
    solver = NeuralPDEOptimizer(num_assets=num_assets, learning_rate=0.01)
    rng_key, subkey = jax.random.split(rng_key)
    
    input_shape = (num_simulations, num_assets)
    params, opt_state = solver.init_params(subkey, input_shape)
    
    loss_history = []
    
    print("Training...")
    for epoch in range(1, 201):  # Tăng lên 200 epochs để thấy rõ hơn
        loss, params, opt_state = solver.train_step(params, opt_state, S_trajectories)
        loss_history.append(float(loss))
        if epoch % 20 == 0:
            print(f"Epoch {epoch}/200 - Loss (Âm Sharpe Ratio): {loss:.4f}")
            
    # Vẽ biểu đồ
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, 201), loss_history, marker='', color='b', linewidth=2)
    plt.title('Quá trình Hội tụ của Mạng Nơ-ron (Neural Solver Loss)')
    plt.xlabel('Epoch')
    plt.ylabel('Loss (Âm Sharpe Ratio)')
    plt.grid(True)
    
    save_path = 'loss_curve.png'
    plt.savefig(save_path)
    print(f"Plot saved to {save_path}")

if __name__ == "__main__":
    run_test()
