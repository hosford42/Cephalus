from typing import Optional, TYPE_CHECKING, Tuple, Callable

import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.models import clone_model

from cephalus.modules.interface import StatePredictionProvider

if TYPE_CHECKING:
    from cephalus.frame import StateFrame
    from cephalus.kernel import StateKernel

__all__ = [
    'StandardStatePredictionProvider',
    'NullStatePredictionProvider',
    'UntrainedStatePredictionProvider',
]


class StandardStatePredictionProvider(StatePredictionProvider):
    """The default state prediction provider. The state model is trained using only the prediction
    losses provided by the other kernel modules, with no intrinsic loss. The state model is cloned
    directly from the configuration's model template without modification."""

    _state_model: Model = None
    _predict_state: Callable = None

    def configure(self, kernel: 'StateKernel') -> None:
        super().configure(kernel)
        self._state_model = clone_model(kernel.config.model_template)

    def build(self) -> None:
        self._state_model.build(input_shape=(None, self.state_width + self.input_width))

        @tf.function
        def predict_state(current_state, current_attended_input):
            sm_in = tf.concat([current_state, current_attended_input], axis=-1)
            return self._state_model(sm_in[tf.newaxis, :])[0]

        self._predict_state = predict_state

        super().build()

    def get_trainable_weights(self) -> Tuple[tf.Variable, ...]:
        return tuple(self._state_model.trainable_weights)

    def get_loss(self, previous_frame: 'StateFrame',
                 current_frame: 'StateFrame') -> Optional[tf.Tensor]:
        return None  # No intrinsic loss.

    def predict_state(self, frame: 'StateFrame') -> Optional[tf.Tensor]:
        return self._predict_state(frame.previous_state, frame.attended_input_tensor)


class NullStatePredictionProvider(StatePredictionProvider):
    """A trivial state prediction provider which ignores its gradients and simply returns the
    initial state unchanged when asked for a new state. This is useful for establishing a baseline
    in experiments, but is probably not what you want to use in production."""

    def configure(self, kernel: 'StateKernel') -> None:
        super().configure(kernel)

    def build(self) -> None:
        super().build()

    def get_trainable_weights(self) -> Tuple[tf.Variable, ...]:
        return ()

    def get_loss(self, previous_frame: 'StateFrame',
                 current_frame: 'StateFrame') -> Optional[tf.Tensor]:
        return None

    def predict_state(self, frame: 'StateFrame') -> Optional[tf.Tensor]:
        return self.kernel.initial_state


class UntrainedStatePredictionProvider(StatePredictionProvider):
    """A trivial state prediction provider which ignores its gradients and never trains its state
    model. This is useful for establishing a baseline in experiments, but is probably not what you
    want to use in production."""

    _state_model: Model = None
    _predict_state: Callable = None

    def configure(self, kernel: 'StateKernel') -> None:
        super().configure(kernel)
        self._state_model = clone_model(kernel.config.model_template)

    def build(self) -> None:
        @tf.function
        def predict_state(current_state, current_attended_input):
            sm_in = tf.concat([current_state, current_attended_input], axis=-1)
            return self._state_model(sm_in[tf.newaxis, :])[0]

        self._predict_state = predict_state

        super().build()

    def get_trainable_weights(self) -> Tuple[tf.Variable, ...]:
        return ()

    def get_loss(self, previous_frame: 'StateFrame',
                 current_frame: 'StateFrame') -> Optional[tf.Tensor]:
        return None

    def predict_state(self, frame: 'StateFrame') -> Optional[tf.Tensor]:
        return self._predict_state(frame.previous_state, frame.attended_input_tensor)
