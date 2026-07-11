import logging
import numpy as np
import torch
from scipy import optimize

logger = logging.getLogger(__name__)

# Device selection: use CUDA if available, otherwise CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def _fgn_correlation_matrix_torch(H: float, n: int) -> torch.Tensor:
    """
    Constructs the Toeplitz correlation matrix for fGn directly on the target device.
    """
    k = torch.arange(n, dtype=torch.float64, device=DEVICE)
    k_plus_1 = torch.abs(k + 1.0)
    k_minus_1 = torch.abs(k - 1.0)
    k_abs = torch.abs(k)
    
    r = 0.5 * (k_plus_1**(2*H) - 2 * k_abs**(2*H) + k_minus_1**(2*H))
    
    # Efficiently construct Toeplitz matrix without loops
    c = torch.arange(n, device=DEVICE)
    r_idx = torch.abs(c.unsqueeze(0) - c.unsqueeze(1))
    return r[r_idx]

def _profile_log_likelihood_torch(H: float, returns_tensor: torch.Tensor) -> float:
    """
    Calculates the negative profile log-likelihood for H using PyTorch.
    returns_tensor: 1D tensor of zero-mean returns.
    """
    n = returns_tensor.shape[0]
    R_H = _fgn_correlation_matrix_torch(H, n)
    
    try:
        # Cholesky decomposition: R_H = L L^T
        # Add a tiny jitter to the diagonal for numerical stability, especially for H close to 0 or 1
        jitter = torch.eye(n, dtype=torch.float64, device=DEVICE) * 1e-8
        L = torch.linalg.cholesky(R_H + jitter)
    except Exception:
        # Not positive definite or other linear algebra error
        return float('inf')

    # Calculate log determinant: log|R_H| = 2 * sum(log(diag(L)))
    log_det = 2.0 * torch.sum(torch.log(torch.diag(L)))
    
    # Calculate X^T R_H^{-1} X
    # returns_tensor is (n,), we need (n, 1) for cholesky_solve
    x_col = returns_tensor.unsqueeze(1)
    
    # cholesky_solve returns R_H^{-1} x. Then we dot it with X^T.
    inv_R_H_x = torch.cholesky_solve(x_col, L)
    
    quad_form = torch.matmul(returns_tensor.unsqueeze(0), inv_R_H_x).squeeze()
    
    if quad_form <= 0:
        return float('inf')
        
    # The profile negative log-likelihood
    val = (1.0 / n) * log_det + torch.log(quad_form)
    return val.item()

def estimate_hurst_mle(prices: np.ndarray, max_points: int = 10000) -> float:
    """
    Estimates the Hurst exponent using Maximum Likelihood Estimation on Fractional Gaussian Noise.
    Utilizes PyTorch for O(N^3) matrix operations, allowing max_points to be safely set 
    much higher (e.g., 10000) for far greater accuracy.
    """
    if len(prices) > max_points:
        prices = prices[-max_points:]
        
    # Calculate log returns
    returns = np.diff(np.log(prices))
    
    # Demean returns
    returns = returns - np.mean(returns)
    
    if np.all(returns == 0) or len(returns) < 10:
        return 0.5
        
    # Pre-load the returns array to the target device (GPU if available)
    returns_tensor = torch.tensor(returns, dtype=torch.float64, device=DEVICE)
    
    def objective(x):
        return _profile_log_likelihood_torch(x, returns_tensor)
        
    try:
        res = optimize.minimize_scalar(
            objective, 
            bounds=(0.01, 0.99), 
            method='bounded',
            options={'xatol': 1e-4, 'maxiter': 100}
        )
        if res.success:
            return float(res.x)
        else:
            logger.warning(f"MLE optimization failed: {res.message}")
            return 0.5
    except Exception as e:
        logger.error(f"Error in MLE Hurst estimation: {e}")
        return 0.5
