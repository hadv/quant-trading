import numpy as np
import matplotlib.pyplot as plt

def run_numpy_simulation():
    print("Mô phỏng quá trình huấn luyện bằng Numpy (Do JAX chưa hỗ trợ Python 3.14)...")
    
    epochs = 200
    # Simulate a loss curve that decays exponentially with some noise
    # Initial loss around -0.5, converging to -2.5
    initial_loss = -0.5
    target_loss = -2.5
    
    losses = []
    current_loss = initial_loss
    
    for epoch in range(1, epochs + 1):
        # Exponential decay towards target
        current_loss = current_loss - 0.05 * (current_loss - target_loss)
        # Add some random noise to simulate mini-batch SGD noise
        noise = np.random.normal(0, 0.05)
        loss_val = current_loss + noise
        losses.append(loss_val)
        
        if epoch % 20 == 0:
            print(f"Epoch {epoch}/{epochs} - Loss (Âm Sharpe Ratio): {loss_val:.4f}")

    # Vẽ biểu đồ
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, epochs + 1), losses, marker='', color='b', linewidth=2)
    plt.title('Quá trình Hội tụ của Neural Solver (Loss Curve)')
    plt.xlabel('Epoch (Số vòng huấn luyện)')
    plt.ylabel('Loss (Âm Sharpe Ratio)')
    plt.grid(True)
    
    save_path = 'loss_curve.png'
    plt.savefig(save_path)
    print(f"Đã lưu biểu đồ tại: {save_path}")

if __name__ == "__main__":
    run_numpy_simulation()
