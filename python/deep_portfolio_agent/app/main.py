import time
from app.data_loader import DataLoader
from app.config import config

def run_agent():
    print("Starting Deep Portfolio Agent (JAX Backend)...")
    loader = DataLoader()
    
    while True:
        try:
            # 1. Tải danh sách tài sản tốt nhất
            assets = loader.load_top_100_assets()
            
            # 2. Tải lịch sử giá
            df_prices = loader.load_historical_candles(assets)
            
            # 3. Tính toán ma trận hiệp phương sai và kỳ vọng (Inputs cho Neural/Monte Carlo)
            mean_returns, cov_matrix = loader.calculate_returns_and_covariance(df_prices)
            
            print(f"Data loaded successfully. Mean Returns shape: {mean_returns.shape}, Cov Matrix shape: {cov_matrix.shape}")
            
            # --- PHASE 2: JAX MONTE CARLO & NEURAL SOLVER ---
            import jax
            import jax.numpy as jnp
            from app.models.sde_simulator import SDESimulator
            from app.models.neural_solver import NeuralPDEOptimizer
            
            num_assets = len(assets)
            num_simulations = config.NUM_SIMULATIONS
            
            print("Khởi tạo SDESimulator và chạy 10,000 kịch bản vũ trụ...")
            sde = SDESimulator(num_assets=num_assets, num_simulations=num_simulations, num_steps=21)
            rng_key = jax.random.PRNGKey(42)
            rng_key, subkey = jax.random.split(rng_key)
            
            # Lấy giá hiện tại (Mock S0 = 100 cho tất cả)
            S0_array = jnp.ones(num_assets) * 100.0
            
            # Mô phỏng SDE
            S_trajectories = sde.simulate_gbm(subkey, S0_array, jnp.array(mean_returns), jnp.array(cov_matrix))
            print(f"Hoàn tất mô phỏng Monte Carlo. Shape quỹ đạo: {S_trajectories.shape}")
            
            print("Khởi tạo Neural Solver và tối ưu hóa danh mục...")
            solver = NeuralPDEOptimizer(num_assets=num_assets)
            rng_key, subkey = jax.random.split(rng_key)
            
            # Input của model là giá hiện tại S0
            input_shape = (num_simulations, num_assets)
            params, opt_state = solver.init_params(subkey, input_shape)
            
            # Train loop (VD: 100 epochs)
            for epoch in range(1, 101):
                loss, params, opt_state = solver.train_step(params, opt_state, S_trajectories)
                if epoch % 20 == 0:
                    print(f"Epoch {epoch}/100 - Loss (Âm Sharpe Ratio): {loss:.4f}")
            
            # Lấy tỷ trọng mục tiêu cuối cùng
            S0_current = jnp.array([df_prices[sym].iloc[-1] for sym in assets])
            target_weights = solver.model.apply(params, S0_current)
            print(f"==> Tỷ trọng mục tiêu tối ưu (Top 5):")
            # Sort and print Top 5 for demo
            import numpy as np
            w_np = np.array(target_weights)
            top_indices = w_np.argsort()[-5:][::-1]
            for idx in top_indices:
                print(f"  {assets[idx]}: {w_np[idx]*100:.2f}%")
            from app.models.risk_manager import RiskManager
            
            # Khởi tạo Risk Manager với độ tin cậy 95%
            risk_manager = RiskManager(confidence_level=0.95)
            var, es = risk_manager.calculate_var_es(target_weights, S_trajectories)
            
            print("\n--- BÁO CÁO RỦI RO (RISK METRICS) ---")
            print(f"Value at Risk (95% VaR): {var*100:.2f}% (Xác suất 95% danh mục KHÔNG LỖ nặng hơn mức này)")
            print(f"Expected Shortfall (ES): {es*100:.2f}% (Nếu kịch bản xấu xảy ra, trung bình sẽ lỗ mức này)")
            
            is_danger, msg = risk_manager.assess_risk(var, es, var_threshold=-0.15)
            if is_danger:
                print(f"🚨 {msg}")
                # TODO: Ghi lệnh Force Sell hoặc chuyển target_weights về 0
            else:
                print(f"✅ {msg}")
            
            print("\nTarget Weights would be written to DB here.")
            
            print("Sleeping for 1 hour before next rebalance...\n")
            time.sleep(3600)
            
        except Exception as e:
            print(f"Error in agent loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_agent()
