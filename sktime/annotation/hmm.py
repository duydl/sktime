"""HMM Annotation Estimator.

Implements a basic Hidden Markov Model (HMM) as an annotation estimator. To read more
about the algorithm, check out the `HMM wikipedia page
<https://en.wikipedia.org/wiki/Hidden_Markov_model>`_.
"""
import warnings
from typing import Tuple

import numpy as np
from scipy.stats import norm

from sktime.annotation.base._base import BaseSeriesAnnotator

__author__ = ["miraep8"]
__all__ = ["HMM"]


class HMM(BaseSeriesAnnotator):
    """Implements a simple HMM fitted with Viterbi algorithm.

    The HMM annotation estimator uses the
    the Viterbi algorithm to fit a sequence of 'hidden state' class
    annotations (represented by an array of integers the same size
    as the observation) to a sequence of observations.

    This is done by finding the most likely path given the emission
    probabilities - (ie the probability that a particular observation
    would be generated by a given hidden state), the transition prob
    (ie the probability of transitioning from one state to another or
    staying in the same state) and the initial probabilities - ie the
    belief of the probability distribution of hidden states at the
    start of the observation sequence).

    Current assumptions/limitations of this implementation:
       - the spacing of time series points is assumed to be equivalent.
       - it only works on univariate data.
       - the emission parameters and transition probabilities are
           assumed to be known.
       - if no initial probs are passed, uniform probabilities are
           assigned (ie rather than the stationary distribution.)
       - requires and returns np.ndarrays.

    _fit is currently empty as the parameters of the probability
    distribution are required to be passed to the algorithm.

    _predict - first the transition_probability and transition_id matrices are
    calculated - these are both nxm matrices, where n is the number of
    hidden states and m is the number of observations. The transition
    probability matrices record the probability of the most likely
    sequence which has observation ``m`` being assigned to hidden state n.
    The transition_id matrix records the step before hidden state n that
    proceeds it in the most likely path.  This logic is mostly carried
    out by helper function _calculate_trans_mats.
    Next, these matrices are used to calculate the most likely
    path (by backtracing from the final mostly likely state and the
    id's that proceeded it.)  This logic is done via a helper func
    hmm_viterbi_label.

    Parameters
    ----------
    emission_funcs : list, shape = [num hidden states]
        List should be of length n (the number of hidden states)
        Either a list of callables [fx_1, fx_2] with signature fx_1(X) -> float
        or a list of callables and matched keyword arguments for those
        callables [(fx_1, kwarg_1), (fx_2, kwarg_2)] with signature
        fx_1(X, **kwargs) -> float (or a list with some mixture of the two).
        The callables should take a value and return a probability when passed
        a single observation. All functions should be properly normalized PDFs
        over the same space as the observed data.
    transition_prob_mat: 2D np.ndarry, shape = [num_states, num_states]
        Each row should sum to 1 in order to be properly normalized
        (ie the j'th column in the i'th row represents the
        probability of transitioning from state i to state j.)
    initial_probs: 1D np.ndarray, shape = [num hidden states], optional
        A array of probabilities that the sequence of hidden states starts in each
        of the hidden states. If passed, should be of length ``n`` the number of
        hidden states and  should match the length of both the emission funcs
        list and the transition_prob_mat. The initial probs should be reflective
        of prior beliefs.  If none is passed will each hidden state will be
        assigned an equal initial prob.

    Attributes
    ----------
    emission_funcs : list, shape = [num_hidden_states]
        The functions to use in calculating the emission probabilities. Taken
        from the __init__ param of same name.
    transition_prob_mat: 2D np.ndarry, shape = [num_states, num_states]
        Matrix of transition probabilities from hidden state to hidden state.
        Taken from the __init__ param of same name.
    initial_probs : 1D np.ndarray, shape = [num_hidden_states]
        Probability over the hidden state identity of the first state. If the
        __init__ param of same name was passed it will take on that value.
        Otherwise it is set to be uniform over all hidden states.
    num_states : int
        The number of hidden states.  Set to be the length of the emission_funcs
        parameter which was passed.
    states : list
        A list of integers from 0 to num_states-1.  Integer labels for the hidden
        states.
    num_obs : int
        The length of the observations data.  Extracted from data.
    trans_prob : 2D np.ndarray, shape = [num_observations, num_hidden_states]
        Shape [num observations, num hidden states]. The max probability that that
        observation is assigned to that hidden state.
        Calculated in _calculate_trans_mat and assigned in _predict.
    trans_id : 2D np.ndarray, shape = [num_observations, num_hidden_states]
        Shape [num observations, num hidden states]. The state id of the state
        proceeding the observation is assigned to that hidden state in the most
        likely path where that occurs. Calculated in _calculate_trans_mat and
        assigned in _predict.

    Examples
    --------
    >>> from sktime.annotation.hmm import HMM
    >>> from scipy.stats import norm
    >>> from numpy import asarray
    >>> # define the emission probs for our HMM model:
    >>> centers = [3.5,-5]
    >>> sd = [.25 for i in centers]
    >>> emi_funcs = [(norm.pdf, {'loc': mean,
    ...  'scale': sd[ind]}) for ind, mean in enumerate(centers)]
    >>> hmm_est = HMM(emi_funcs, asarray([[0.25,0.75], [0.666, 0.333]]))
    >>> # generate synthetic data (or of course use your own!)
    >>> obs = asarray([3.7,3.2,3.4,3.6,-5.1,-5.2,-4.9])
    >>> hmm_est = hmm_est.fit(obs)
    >>> labels = hmm_est.predict(obs)
    """

    # plan to update to make multivariate.
    _tags = {
        "univariate-only": True,
        "fit_is_empty": True,
        "task": "segmentation",
        "learning_type": "unsupervised",
    }

    def __init__(
        self,
        emission_funcs: list,
        transition_prob_mat: np.ndarray,
        initial_probs: np.ndarray = None,
    ):
        self.initial_probs = initial_probs
        self.emission_funcs = emission_funcs
        self.transition_prob_mat = transition_prob_mat
        super().__init__()
        self._validate_init()

    def _validate_init(self):
        """Verify the parameters passed to init.

        Tests/Assumptions:
            - the length of initial_probs, emission_funcs, and the
            size of transition_prob_mat are all the same.
            - transition_prob_mat is square.
            - all the rows of transition_prob_mat sum to 1.
            - if passed initial_probs, is all sums to 1.
        """
        tran_mat_len = self.transition_prob_mat.shape[0]
        # transition_prob_mat should be square:
        if (
            self.transition_prob_mat.ndim != 2
            or tran_mat_len != self.transition_prob_mat.shape[1]
        ):
            raise ValueError(
                "Transition Probability must be 2D square, but got an"
                f"object of size {self.transition_prob_mat.shape}"
            )
        # number of states should be consistent!
        if self.initial_probs is not None:
            init_prob_len = len(self.initial_probs)
        else:
            # if init-prob_lens is None, it will be generated with this len:
            init_prob_len = len(self.emission_funcs)
        if not tran_mat_len == len(self.emission_funcs) == init_prob_len:
            raise ValueError(
                "Number of hidden states is inconsistent!  emission_funcs "
                f" was of length {len(self.emission_funcs)} transition_prob_mat was "
                f" of length {tran_mat_len} and the length of the passed "
                f" (or generated) list of initial probabilities was "
                f" {init_prob_len}. All of these lengths should be the same"
                f" as they all correspond to the same underlying list of hidden"
                f" states."
            )
        # sum of all rows in transition_prob_mat should be 1.
        if not np.isclose(
            np.ones(tran_mat_len),
            np.sum(self.transition_prob_mat, axis=1),
            rtol=5e-2,
        ).all():
            raise ValueError("The sum of all rows in the transition matrix must be 1.")
        # sum of all initial_probs should be 1 if it is provided.
        if self.initial_probs is not None and sum(self.initial_probs) != 1:
            raise ValueError("Sum of initial probs should be 1.")

    @staticmethod
    def _calculate_trans_mats(
        initial_probs: np.ndarray,
        emi_probs: np.ndarray,
        transition_prob_mat: np.ndarray,
        num_obs: int,
        num_states: int,
    ) -> Tuple[np.array, np.array]:
        """Calculate the transition mats used in the Viterbi algorithm.

        Parameters
        ----------
        initial_probs : 1D np.ndarray, shape = [num_hidden_states]
            A nx1 dimensional array of floats where n
            represents the number of hidden states in the model. It
            contains the probability that hidden state for the state
            before the first observation was state n.  Should sum to 1.
        emi_probs : 2D np.ndarray, shape = [num_observations, num_hidden_states]
            A nxm dimensional arrayof floats, where n is the
            number of hidden states and m is the number of observations.
            For a given observation, it should contain the probability that it
            could havbe been generated (ie emitted) from each of the hidden states
            Each entry should be between 0 and 1
        transition_prob_mat : 2D np.ndarray, shape = [num_states, num_states]
            A nxn dimensional array of floats where n is
            the number of hidden states in the model. The jth col in the ith row
            represents the probability of transitioning to state j from state i.
            Thus each row should sum to 1.
        num_obs : int,
            the number of observations (m)
        num_states : int,
            the number of hidden states (n)

        Returns
        -------
        trans_prob : 2D np.ndarray, shape = [num_observations, num_hidden_states]
            an nxm dimensional array which represents the
            maximum probability of the hidden state of observation m is state n.
        trans_id : 2D np.ndarray, shape = [num_observations, num_hidden_states]
            a nxm dimensional array which for each observation
            "i" and state "j" the i,j entry records the state_id of the most
            likely state that could have led to the hidden state being "i" for
            observation "j".
        """
        # trans_prob represents the maximum probability of being in that
        # state at that stage
        trans_prob = np.zeros((num_states, num_obs))
        trans_prob[:, 0] = np.log(initial_probs) + np.log(emi_probs[:, 0])

        # trans_id is the index of the state that would have been the most
        # likely preceding state.
        trans_id = np.zeros((num_states, num_obs), dtype=np.int32)

        # use Vertibi Algorithm to fill in trans_prob and trans_id:
        for i in range(1, num_obs):
            # adds log(transition_prob_mat) element-wise:
            paths = np.log(transition_prob_mat)
            # adds the probabilities for the state before columns wise:
            paths += np.stack(
                [trans_prob[:, i - 1] for _ in range(num_states)], axis=0
            ).T
            # adds the probabilities from emission row wise:
            paths += np.stack(
                [np.log(emi_probs[:, i]) for _ in range(num_states)], axis=0
            )
            trans_id[:, i] = np.argmax(paths, axis=0)
            trans_prob[:, i] = np.max(paths, axis=0)

        if np.any(np.isinf(trans_prob[:, -1])):
            warnings.warn(
                "Change parameters, the distribution doesn't work",
                stacklevel=2,
            )

        return trans_prob, trans_id

    @staticmethod
    def _make_emission_probs(
        emission_funcs: list, observations: np.ndarray
    ) -> np.ndarray:
        """Calculate the prob each obs comes from each hidden state.

        Parameters
        ----------
        emission_funcs : list, shape = [num_hidden_states]
            List should be of length n (the number of hidden states)
            Either a list of callables [fx_1, fx_2] with signature fx_1(X) -> float
            or a list of callables and matched keyword arguments for those
            callables [(fx_1, kwarg_1), (fx_2, kwarg_2)] with signature
            fx_1(X, **kwargs) -> float (or a list with some mixture of the two).
            The callables should take a value and return a probability when passed
            a single observation. All functions should be properly normalized PDFs
            over the same space as the observed data.
        observations : 1D np.ndarray, shape = [num_observations]
            Observations to apply labels to.

        Returns
        -------
        emi_probs : 2D np.ndarray, shape = [num_observations, num_hidden_states]
            A nxm dimensional arrayof floats, where n is the
            number of hidden states and m is the number of observations.
            For a given observation, it contains the probability that it
            could havbe been generated (ie emitted) from each of the hidden states
            Each entry should be between 0 and 1
        """
        # assign emission probabilities from each state to each position:

        emi_probs = np.zeros(shape=(len(emission_funcs), len(observations)))
        for state_id, emission in enumerate(emission_funcs):
            if isinstance(emission, tuple):
                emission_func = emission[0]
                kwargs = emission[1]
                emi_probs[state_id, :] = np.array(
                    [emission_func(x, **kwargs) for x in observations]
                )
            else:
                emi_probs[state_id, :] = np.array([emission(x) for x in observations])
        return emi_probs

    @staticmethod
    def _hmm_viterbi_label(
        num_obs: int, states: list, trans_prob: np.ndarray, trans_id: np.ndarray
    ) -> np.array:
        """Assign hidden state ids to all observations based on most likely path.

        Parameters
        ----------
        num_obs : int,
            the number of observations.
        states : list,
            a list with integer ids to assign to each hidden state.
        trans_prob :np.ndarray,
            a matrix of size [number of observations, number of hidden states]
            which contains the highest probability path that leads to
            observation m being assigned to hidden state n.
        trans_id : np.ndarray, shape = [num_observations, num_hidden_states]
            a matrix of size [number of observations, number of hidden states]
            which contains the state id of the state proceeding this one on the
            most likely path that has observation m being assigned to hidden
            state n.

        Returns
        -------
        hmm_fit: np.ndarray, shape = [num_observations]
            an array of shape [length of the X (obs)].
            each entry in the array is an int representing a hidden id state
            that has been assigned to that observation.
        """
        hmm_fit = np.zeros(num_obs)
        # Now we trace backwards and find the most likely path:
        max_inds = np.zeros(num_obs, dtype=np.int32)
        max_inds[-1] = np.argmax(trans_prob[:, -1])
        hmm_fit[-1] = states[max_inds[-1]]
        for index in range(num_obs - 1, 0, -1):
            max_inds[index - 1] = trans_id[max_inds[index], index]
            hmm_fit[index - 1] = states[max_inds[index - 1]]
        return hmm_fit

    def _fit(self, X, Y=None):
        """Do nothing, currently empty.

        Parameters
        ----------
        X : 1D np.array, shape = [num_observations]
            Observations to apply labels to.

        Returns
        -------
        self :
            Reference to self.
        """
        return self

    def _predict(self, X):
        """Determine the most likely seq of hidden states by Viterbi algorithm.

        Parameters
        ----------
        X : 1D np.array, shape = [num_observations]
            Observations to apply labels to.

        Returns
        -------
        annotated_x : array-like, shape = [num_observations]
            Array of predicted class labels, same size as input.
        """
        self.num_states = len(self.emission_funcs)
        self.states = list(range(self.num_states))
        self.num_obs = len(X)
        emi_probs = self._make_emission_probs(self.emission_funcs, X)
        init_probs = self.initial_probs
        if self.initial_probs is None:
            init_probs = 1.0 / self.num_states * np.ones(self.num_states)
        trans_prob, trans_id = self._calculate_trans_mats(
            init_probs,
            emi_probs,
            self.transition_prob_mat,
            self.num_obs,
            self.num_states,
        )

        self.trans_prob = trans_prob
        self.trans_id = trans_id
        return self._hmm_viterbi_label(
            self.num_obs, self.states, self.trans_prob, self.trans_id
        )

    @classmethod
    def get_test_params(cls, parameter_set="default"):
        """Return testing parameter settings for the estimator.

        Parameters
        ----------
        parameter_set : str, default="default"
            Name of the set of test parameters to return, for use in tests. If no
            special parameters are defined for a value, will return ``"default"`` set.

        Returns
        -------
        params : dict or list of dict
        """
        centers = [3.5, -5]
        sd = [100 for _ in centers]
        emi_funcs = [
            (norm.pdf, {"loc": mean, "scale": sd[ind]})
            for ind, mean in enumerate(centers)
        ]

        trans_mat = np.asarray([[0.25, 0.75], [0.666, 0.333]])
        params_1 = {"emission_funcs": emi_funcs, "transition_prob_mat": trans_mat}
        params_2 = {
            "emission_funcs": emi_funcs,
            "transition_prob_mat": trans_mat,
            "initial_probs": np.asarray([0.2, 0.8]),
        }

        return [params_1, params_2]
