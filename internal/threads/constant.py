"""Threads module constants."""

# Depth thresholds for classifying mention roles within a thread.
# Mirrors UAPType semantics from core-analysis without importing that enum.
DEPTH_POST = 0  # root-level post / video / news / feedback
DEPTH_COMMENT = 1  # direct reply to root
DEPTH_REPLY_MIN = 2  # reply to a comment or deeper

__all__ = ["DEPTH_POST", "DEPTH_COMMENT", "DEPTH_REPLY_MIN"]
