"""The forecast() report includes chronological holdout MAE, RMSE, and R²."""
try:
    from .predict import forecast
except ImportError:
    from predict import forecast

__all__ = ["forecast"]
