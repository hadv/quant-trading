import time
import logging
from app.data_loader import DataLoader
from app.config import config
from app.telemetry import init_telemetry, tracer, rebalance_counter, var_95_gauge, es_gauge

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("deep-portfolio-agent")

def run_agent():
    logger.info("Starting Deep Portfolio Agent (JAX Backend with OpenTelemetry)...")
    init_telemetry("deep-portfolio-agent")
    loader = DataLoader()
    
    while True:
        try:
            with tracer.start_as_current_span("portfolio_rebalance_cycle") as cycle_span:
                # 1. Tải danh sách tài sản tốt nhất & lịch sử giá
                with tracer.start_as_current_span("load_market_data"):
                    assets = loader.load_top_100_assets()
                    df_prices = loader.load_historical_candles(assets)
                    mean_returns, cov_matrix = loader.calculate_returns_and_covariance(df_prices)
                
                logger.info(f"Data loaded successfully. Assets: {len(assets)}, Mean Returns shape: {mean_returns.shape}, Cov Matrix shape: {cov_matrix.shape}")
                
                # --- PHASE 2: JAX MONTE CARLO & NEURAL SOLVER ---
                import jax
                import jax.numpy as jnp
                from app.models.sde_simulator import SDESimulator
                from app.models.neural_solver import NeuralPDEOptimizer
                
                num_assets = len(assets)
                num_simulations = config.NUM_SIMULATIONS
                
                with tracer.start_as_current_span("monte_carlo_sde_simulation") as sde_span:
                    logger.info("Khởi tạo SDESimulator và chạy kịch bản Monte Carlo...")
                    sde = SDESimulator(num_assets=num_assets, num_simulations=num_simulations, num_steps=21)
                    rng_key = jax.random.PRNGKey(42)
                    rng_key, subkey = jax.random.split(rng_key)
                    
                    # Lấy giá hiện tại (Mock S0 = 100 cho tất cả)
                    S0_array = jnp.ones(num_assets) * 100.0
                    
                    # Mô phỏng SDE
                    S_trajectories = sde.simulate_gbm(subkey, S0_array, jnp.array(mean_returns), jnp.array(cov_matrix))
                    sde_span.set_attribute("sde.num_simulations", num_simulations)
                    sde_span.set_attribute("sde.num_assets", num_assets)
                    logger.info(f"Hoàn tất mô phỏng Monte Carlo. Shape quỹ đạo: {S_trajectories.shape}")
                
                with tracer.start_as_current_span("neural_pde_solver_training") as train_span:
                    logger.info("Khởi tạo Neural Solver và tối ưu hóa danh mục...")
                    solver = NeuralPDEOptimizer(num_assets=num_assets)
                    rng_key, subkey = jax.random.split(rng_key)
                    
                    # Input của model là giá hiện tại S0
                    input_shape = (num_simulations, num_assets)
                    params, opt_state = solver.init_params(subkey, input_shape)
                    
                    # Train loop (100 epochs)
                    for epoch in range(1, 101):
                        loss, params, opt_state = solver.train_step(params, opt_state, S_trajectories)
                        if epoch % 20 == 0:
                            logger.info(f"Epoch {epoch}/100 - Loss (Âm Sharpe Ratio): {loss:.4f}")
                    
                    train_span.set_attribute("neural_solver.final_loss", float(loss))
                
                # Lấy tỷ trọng mục tiêu cuối cùng
                S0_current = jnp.array([df_prices[sym].iloc[-1] for sym in assets])
                target_weights = solver.model.apply(params, S0_current)
                logger.info("==> Tỷ trọng mục tiêu tối ưu (Top 5):")
                import numpy as np
                w_np = np.array(target_weights)
                top_indices = w_np.argsort()[-5:][::-1]
                for idx in top_indices:
                    logger.info(f"  {assets[idx]}: {w_np[idx]*100:.2f}%")
                    
                with tracer.start_as_current_span("risk_management_assessment") as risk_span:
                    from app.models.risk_manager import RiskManager
                    
                    # Khởi tạo Risk Manager với độ tin cậy 95%
                    risk_manager = RiskManager(confidence_level=0.95)
                    var, es = risk_manager.calculate_var_es(target_weights, S_trajectories)
                    
                    logger.info("\n--- BÁO CÁO RỦI RO (RISK METRICS) ---")
                    logger.info(f"Value at Risk (95% VaR): {var*100:.2f}%")
                    logger.info(f"Expected Shortfall (ES): {es*100:.2f}%")
                    
                    is_danger, msg = risk_manager.assess_risk(var, es, var_threshold=-0.15)
                    if is_danger:
                        logger.warning(f"🚨 {msg}")
                    else:
                        logger.info(f"✅ {msg}")
                    
                    risk_span.set_attribute("risk.var_95", float(var))
                    risk_span.set_attribute("risk.expected_shortfall", float(es))
                    risk_span.set_attribute("risk.is_danger", is_danger)

                # Record OTel Metrics
                rebalance_counter.add(1)
                var_95_gauge.set(float(var) * 100)
                es_gauge.set(float(es) * 100)
                
                logger.info("Target Weights would be written to DB here.")
                logger.info("Sleeping for 1 hour before next rebalance...\n")
                
            time.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in agent loop: {e}", exc_info=True)
            time.sleep(60)

if __name__ == "__main__":
    run_agent()
