from dataclasses import dataclass, field
from typing import Optional, List, Union, Dict, Any, TYPE_CHECKING

import tensorflow as tf

if TYPE_CHECKING:
    from cephalus.modules.interface import StateKernelModule, InputSample

__all__ = [
    'StateFrame'
]


# TODO: Consider renaming StateFrame to StateDecision, or ActionDecision to ActionFrame, to
#       emphasize their parallel nature.

@dataclass
class StateFrame:
    """A collection of all the information collected about a state prediction which may be required
    to train the kernel. Kernels may subclass this and add their own fields."""

    stream_id: str  # Useful for tracing/debugging
    previous_state: Union[tf.Tensor, tf.Variable]
    tape: Optional[tf.GradientTape]

    clock_ticks: int = 0

    input_samples: List['InputSample'] = None
    attended_input_tensor: tf.Tensor = None
    current_state: Optional[tf.Tensor] = None

    # The combined loss of the current state, including discounted estimated future loss. Analogous
    # to the update target for `Q(s_t, a_t)`, i.e.
    # `r_t + discount * Q(s_(t+1), a_(t+1))` in SARSA or
    # `r_t + discount * max(Q(s_(t+1), a) for a in A)` in Q-learning.
    combined_loss: Optional[tf.Tensor] = None

    trained: bool = False

    module_data: Dict['StateKernelModule', Dict[str, Any]] = field(default_factory=dict)
