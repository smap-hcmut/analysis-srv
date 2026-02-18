from dataclasses import dataclass


@dataclass
class PublishConfig:
    topic: str = ""
    batch_size: int = 10
    flush_interval_seconds: float = 5.0
    enabled: bool = True
