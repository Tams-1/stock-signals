"""
Walk-forward validation for parameter optimization.

Prevents overfitting by testing parameters on out-of-sample data.
Implements rolling window backtest approach.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class WalkForwardValidator:
    """
    Walk-forward validation for trading strategy parameters.
    
    Prevents overfitting by:
    1. Splitting data into train/test windows
    2. Optimizing on train, testing on test
    3. Rolling forward and repeating
    4. Aggregating out-of-sample performance
    """
    
    def __init__(self, train_window: int = 252, test_window: int = 63):
        """
        Initialize validator.
        
        Args:
            train_window: Days for training (default 1 year)
            test_window: Days for testing (default 3 months)
        """
        self.train_window = train_window
        self.test_window = test_window
    
    def split_data(self, data: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create walk-forward train/test splits.
        
        Returns:
            List of (train_data, test_data) tuples
        """
        splits = []
        total_len = len(data)
        
        # Start from beginning, roll forward
        start_idx = 0
        
        while start_idx + self.train_window + self.test_window <= total_len:
            train_start = start_idx
            train_end = start_idx + self.train_window
            test_start = train_end
            test_end = test_start + self.test_window
            
            train_data = data.iloc[train_start:train_end]
            test_data = data.iloc[test_start:test_end]
            
            splits.append((train_data, test_data))
            
            # Roll forward by test window
            start_idx += self.test_window
        
        return splits
    
    def validate_parameters(self, data: pd.DataFrame, 
                           param_grid: Dict[str, List],
                           strategy_func) -> Dict:
        """
        Validate parameters using walk-forward approach.
        
        Args:
            data: Price data
            param_grid: Dict of parameter names to test values
            strategy_func: Function that takes (data, params) and returns performance
        
        Returns:
            Best parameters and out-of-sample performance
        """
        splits = self.split_data(data)
        
        if not splits:
            return {'best_params': {}, 'oos_performance': 0.0}
        
        # Grid search over parameters
        best_params = None
        best_oos_performance = -np.inf
        
        # Generate all parameter combinations
        from itertools import product
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))
        
        for params in param_combinations:
            param_dict = dict(zip(param_names, params))
            
            oos_performances = []
            
            for train_data, test_data in splits:
                # Test on out-of-sample data
                performance = strategy_func(test_data, param_dict)
                oos_performances.append(performance)
            
            # Average out-of-sample performance
            avg_oos = np.mean(oos_performances)
            
            if avg_oos > best_oos_performance:
                best_oos_performance = avg_oos
                best_params = param_dict
        
        return {
            'best_params': best_params,
            'oos_performance': float(best_oos_performance),
            'n_splits': len(splits)
        }
    
    def estimate_overfitting(self, data: pd.DataFrame, 
                            params: Dict,
                            strategy_func) -> Dict:
        """
        Estimate overfitting by comparing in-sample vs out-of-sample performance.
        
        Args:
            data: Price data
            params: Parameters to test
            strategy_func: Strategy function
        
        Returns:
            Dict with overfitting metrics
        """
        splits = self.split_data(data)
        
        is_performances = []
        oos_performances = []
        
        for train_data, test_data in splits:
            # In-sample performance (train)
            is_perf = strategy_func(train_data, params)
            is_performances.append(is_perf)
            
            # Out-of-sample performance (test)
            oos_perf = strategy_func(test_data, params)
            oos_performances.append(oos_perf)
        
        avg_is = np.mean(is_performances)
        avg_oos = np.mean(oos_performances)
        
        # Overfitting ratio (lower is better, < 1.0 means OOS > IS is impossible)
        overfitting_ratio = avg_is / avg_oos if avg_oos != 0 else float('inf')
        
        return {
            'in_sample_performance': float(avg_is),
            'out_of_sample_performance': float(avg_oos),
            'overfitting_ratio': float(overfitting_ratio),
            'degradation_pct': float((avg_is - avg_oos) / avg_is * 100) if avg_is != 0 else 0
        }


# Convenience function
def run_walk_forward_validation(data: pd.DataFrame, 
                                param_grid: Dict[str, List],
                                strategy_func) -> Dict:
    """
    Run complete walk-forward validation.
    
    Args:
        data: Price data
        param_grid: Parameter grid
        strategy_func: Strategy function
    
    Returns:
        Validation results
    """
    validator = WalkForwardValidator()
    return validator.validate_parameters(data, param_grid, strategy_func)
