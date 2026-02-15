"""Interface for Analytics Pipeline."""

from typing import Protocol, runtime_checkable

from .type import Input, Output


@runtime_checkable
class IAnalyticsPipeline(Protocol):
    """Protocol for analytics pipeline orchestration.
    
    This interface defines the contract for processing social media posts
    through the full analytics pipeline.
    """

    def process(self, input_data: Input) -> Output:
        """Process a single post through the analytics pipeline.
        
        Args:
            input_data: Input structure containing post data
            
        Returns:
            Output with analytics results and metadata
            
        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        ...


__all__ = ["IAnalyticsPipeline"]
