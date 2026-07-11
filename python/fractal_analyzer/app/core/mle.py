import logging
import numpy as np
from scipy import optimize
from scipy.linalg import toeplitz, cho_factor, cho_solve

logger = logging.getLogger(__name__)

def _fgn_autocovariance(H: float, n: int) -> np.ndarray:
    """
    Computes the auto-covariance sequence for fractional Gaussian noise (fGn).
    """
    k = np.arange(n)
    k_plus_1 = np.abs(k + 1.0)
    k_minus_1 = np.abs(k - 1.0)
    k_abs = np.abs(k)
    
    return 0.5 * (k_plus_1**(2*H) - 2 * k_abs**(2*H) + k_minus_1**(2*H))

def _fgn_correlation_matrix(H: float, n: int) -> np.ndarray:
    """
    Constructs the Toeplitz correlation matrix for fGn.
    """
    r = _fgn_autocovariance(H, n)
    return toeplitz(r)

def _profile_log_likelihood(H: float, returns: np.ndarray) -> float:
    """
    Calculates the negative profile log-likelihood for H.
    returns: array-like of zero-mean returns.
    """
    n = len(returns)
    R_H = _fgn_correlation_matrix(H, n)
    
    try:
        # Cholesky decomposition of R_H: R_H = L L^T
        L, lower = cho_factor(R_H, lower=True)
    except Exception:
        # If matrix is not positive definite
        return np.inf

    # Calculate log determinant: log|R_H| = 2 * sum(log(diag(L)))
    log_det = 2.0 * np.sum(np.log(np.diag(L)))
    
    # Calculate X^T R_H^{-1} X using cholesky solver
    quad_form = np.dot(returns, cho_solve((L, lower), returns))
    
    if quad_form <= 0:
        return np.inf
        
    # The profile negative log-likelihood (ignoring constants)
    return (1.0 / n) * log_det + np.log(quad_form)

def estimate_hurst_mle(prices: np.ndarray, max_points: int = 400) -> float:
    """
    Estimates the Hurst exponent using Maximum Likelihood Estimation on Fractional Gaussian Noise.
    If the number of points exceeds max_points, it uses the most recent max_points 
    to reflect the current market regime and ensure computational efficiency.
    """
    # Use the most recent max_points to reflect current regime and keep O(N^3) fast
    if len(prices) > max_points:
        prices = prices[-max_points:]
        
    # Calculate log returns
    returns = np.diff(np.log(prices))
    
    # Demean returns
    returns = returns - np.mean(returns)
    
    if np.all(returns == 0) or len(returns) < 10:
        return 0.5
        
    def objective(x):
        return _profile_log_likelihood(x, returns)
        
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
