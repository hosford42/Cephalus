from typing import Union, Optional, TYPE_CHECKING, Tuple, Callable

import tensorflow as tf

from cephalus.modeled import Modeled
from cephalus.q.action_policies import ActionPolicy, ActionDecision

if TYPE_CHECKING:
    from cephalus.q.probabilistic_models import ProbabilisticModel


class TDAgent(Modeled):
    max_observable_reward: float = None
    min_observable_reward: float = None
    episodes: int = 0
    total_steps: int = 0

    def __init__(self, q_model: 'ProbabilisticModel', action_policy: ActionPolicy,
                 discount: Union[float, Callable[[float, float], float]],
                 stabilize: bool = True):
        self._q_model = q_model
        self._action_policy = action_policy
        self.discount = discount
        self.stabilize = stabilize
        self._previous_decision = None
        self._current_decision = None

    @property
    def q_model(self) -> 'ProbabilisticModel':
        return self._q_model

    @property
    def action_policy(self) -> ActionPolicy:
        return self._action_policy

    def clone(self) -> 'TDAgent':
        return type(self)(self._q_model, self._action_policy, self.discount, self.stabilize)

    def get_discount(self) -> float:
        if callable(self.discount):
            return self.discount(self.episodes, self.total_steps)
        else:
            assert isinstance(self.discount, float)
            return self.discount

    def build(self) -> None:
        self._q_model.build()
        self._action_policy.build()

    def get_trainable_weights(self) -> Tuple[tf.Variable, ...]:
        return self._q_model.get_trainable_weights() + self._action_policy.get_trainable_weights()

    def _update_previous_decision(self) -> None:
        if not self._previous_decision:
            return None

        assert self._previous_decision.reward is not None
        assert self._previous_decision.q_value_target is None

        if self._current_decision:
            assert self._current_decision.reward is None
            prediction = self._current_decision.exploit_q_value_prediction
            prediction_confidence = self._current_decision.exploit_confidence
            discount = self.get_discount()

            # Sometimes the model can generalize poorly, resulting in values that are outside
            # the bounds of what is actually reasonable.
            if self.stabilize:
                if self.min_observable_reward is not None:
                    prediction = tf.maximum(prediction, self.min_observable_reward)
                if self.max_observable_reward is not None:
                    prediction = tf.minimum(prediction, self.max_observable_reward)
                previous_q_value = ((self._previous_decision.reward + discount * prediction) /
                                    (1.0 + discount))
            else:
                previous_q_value = self._previous_decision.reward + discount * prediction
        else:
            prediction_confidence = 1.0
            if self.stabilize:
                discount = self.get_discount()
                previous_q_value = self._previous_decision.reward / (1.0 + discount)
            else:
                previous_q_value = self._previous_decision.reward

        self._previous_decision.q_value_target = previous_q_value
        self._previous_decision.q_value_target_confidence = prediction_confidence

    def _close_previous_decision(self) -> Optional[tf.Tensor]:
        if self._previous_decision:
            # TODO: Use logging.
            print("Previous step's predicted Q-value for task TDAgent:",
                  self._previous_decision.selected_q_value_prediction.numpy())
            print("Previous step's target Q-value for task TDAgent:",
                  float(self._previous_decision.q_value_target))
            loss = self._action_policy.get_loss(self._previous_decision)
        else:
            loss = None
        self._previous_decision = self._current_decision
        self._current_decision = None
        return loss

    def reset(self) -> Optional[tf.Tensor]:
        self.episodes += 1
        self._update_previous_decision()

        # We have to treat a reset as an observation of reward zero, because the bounds we're
        # establishing apply to q value predictions, not rewards, and we use a q value prediction
        # of zero for end-of-episode.
        if self.stabilize:
            reward = 0.0

            if self.max_observable_reward is None:
                self.max_observable_reward = reward
            else:
                self.max_observable_reward = max(reward, self.max_observable_reward)
            if self.min_observable_reward is None:
                self.min_observable_reward = reward
            else:
                self.min_observable_reward = min(reward, self.min_observable_reward)

            print("Max observable reward:", self.max_observable_reward)
            print("Min observable reward:", self.min_observable_reward)

        return self._close_previous_decision()

    def choose_action(self, state_input: tf.Tensor):
        assert self._current_decision is None

        step = self._previous_decision.step + 1 if self._previous_decision else 0
        decision = ActionDecision(state_input, self.q_model, step)
        self.action_policy.choose_action(decision)
        self._current_decision = decision

        self._update_previous_decision()

        return decision.selected_action

    def accept_reward(self, reward: Union[float, tf.Tensor]) -> Optional[tf.Tensor]:
        assert self._current_decision is not None
        assert self._current_decision.reward is None

        self.total_steps += 1

        self._current_decision.reward = reward

        if self.stabilize:
            if self.max_observable_reward is None:
                self.max_observable_reward = reward
            else:
                self.max_observable_reward = max(reward, self.max_observable_reward)
            if self.min_observable_reward is None:
                self.min_observable_reward = reward
            else:
                self.min_observable_reward = min(reward, self.min_observable_reward)

            print("Max observable reward:", self.max_observable_reward)
            print("Min observable reward:", self.min_observable_reward)

        return self._close_previous_decision()
