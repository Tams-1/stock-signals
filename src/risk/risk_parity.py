"""
Risk parity and correlation-adjusted position sizing.

Ensures portfolio positions are adjusted for correlation and volatility,
preventing unintended concentration risk.
"""

import numpy as np
import pandas as pd
from typing import Dict, List


class RiskParity:
    """
    Implement risk parity position sizing.
    
    Risk parity allocates positions such that each position contributes
    equally to total portfolio risk, accounting for correlations.
    """
    
    def __init__(self, target_volatility: float = 0.15):
        """
        Initialize risk parity calculator.
        
        Args:
            target_volatility: Target portfolio volatility (default 15% annual)
        """
        self.target_volatility = target_volatility
    
    def calculate_correlation_matrix(self, 
                                     returns_data: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        Calculate correlation matrix from returns data.
        
        Args:
            returns_data: Dict of ticker -> returns series
        
        Returns:
            Correlation matrix DataFrame
        """
        returns_df = pd.DataFrame(returns_data)
        return returns_df.corr()
    
    def calculate_volatility(self, returns: pd.Series) -> float:
        """
        Calculate annualized volatility from returns.
        
        Args:
            returns: Daily returns series
        
        Returns:
            Annualized volatility
        """
        return returns.std() * np.sqrt(252)
    
    def calculate_risk_parity_weights(self,
                                      returns_data: Dict[str, pd.Series]) -> Dict[str, float]:
        """
        Calculate risk parity weights for portfolio.
        
        Uses inverse volatility weighting with correlation adjustment.
        
        Args:
            returns_data: Dict of ticker -> returns series
        
        Returns:
            Dict of ticker -> weight (0-1)
        """
        if not returns_data:
            return {}
        
        # Calculate volatilities
        volatilities = {}
        for ticker, returns in returns_data.items():
            vol = self.calculate_volatility(returns)
            volatilities[ticker] = vol if vol > 0 else 0.20  # Default if can't calculate
        
        # Inverse volatility weighting (simple risk parity)
        inv_vols = {ticker: 1.0 / vol for ticker, vol in volatilities.items()}
        total_inv_vol = sum(inv_vols.values())
        
        # Normalize to weights
        weights = {ticker: inv_vol / total_inv_vol 
                  for ticker, inv_vol in inv_vols.items()}
        
        return weights
    
    def adjust_positions_for_correlation(self,
                                         positions: Dict[str, float],
                                         returns_data: Dict[str, pd.Series]) -> Dict[str, float]:
        """
        Adjust position sizes based on correlation.
        
        Reduces positions in highly correlated assets.
        
        Args:
            positions: Dict of ticker -> position size (0-1)
            returns_data: Dict of ticker -> returns series
        
        Returns:
            Adjusted positions
        """
        if len(positions) <= 1:
            return positions
        
        # Calculate correlation matrix
        corr_matrix = self.calculate_correlation_matrix(returns_data)
        
        adjusted_positions = {}
        
        for ticker, position in positions.items():
            if ticker not in corr_matrix.index:
                adjusted_positions[ticker] = position
                continue
            
            # Calculate average correlation with other positions
            correlations = corr_matrix.loc[ticker].drop(ticker)
            avg_correlation = correlations.mean()
            
            # Reduce position if highly correlated with others
            # Higher correlation = lower position
            if avg_correlation > 0.7:  # High correlation
                adjustment = 0.5  # Cut in half
            elif avg_correlation > 0.5:  # Moderate correlation
                adjustment = 0.75  # Reduce by 25%
            else:  # Low correlation
                adjustment = 1.0  # No adjustment
            
            adjusted_positions[ticker] = position * adjustment
        
        # Renormalize to maintain total exposure
        total_position = sum(adjusted_positions.values())
        if total_position > 1.0:
            # Scale down proportionally
            scale_factor = 1.0 / total_position
            adjusted_positions = {t: p * scale_factor 
                                for t, p in adjusted_positions.items()}
        
        return adjusted_positions
    
    def calculate_portfolio_risk(self,
                                positions: Dict[str, float],
                                returns_data: Dict[str, pd.Series]) -> Dict[str, float]:
        """
        Calculate total portfolio risk accounting for correlations.
        
        Args:
            positions: Dict of ticker -> position weight
            returns_data: Dict of ticker -> returns series
        
        Returns:
            Dict with risk metrics
        """
        if not positions or not returns_data:
            return {'total_risk': 0.0, 'diversification_ratio': 1.0}
        
        # Get aligned returns
        tickers = list(positions.keys())
        returns_df = pd.DataFrame({t: returns_data[t] for t in tickers if t in returns_data})
        
        if returns_df.empty:
            return {'total_risk': 0.0, 'diversification_ratio': 1.0}
        
        # Calculate covariance matrix
        cov_matrix = returns_df.cov() * 252  # Annualized
        
        # Position weights
        weights = np.array([positions.get(t, 0) for t in returns_df.columns])
        
        # Portfolio variance
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        # Diversification ratio (weighted avg vol / portfolio vol)
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_avg_vol = np.dot(weights, individual_vols)
        diversification_ratio = weighted_avg_vol / portfolio_volatility if portfolio_volatility > 0 else 1.0
        
        return {
            'total_risk': float(portfolio_volatility),
            'diversification_ratio': float(diversification_ratio),
            'n_positions': len(tickers)
        }


# Convenience function
def apply_risk_parity(positions: Dict[str, float],
                     returns_data: Dict[str, pd.Series],
                     target_volatility: float = 0.15) -> Dict[str, float]:
    """
    Apply risk parity adjustment to positions.
    
    Args:
        positions: Current positions
        returns_data: Historical returns
        target_volatility: Target portfolio volatility
    
    Returns:
        Risk-adjusted positions
    """
    rp = RiskParity(target_volatility)
    return rp.adjust_positions_for_correlation(positions, returns_data)
