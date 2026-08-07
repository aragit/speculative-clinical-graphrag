"""Property-based tests for SpeculativeGraphRAG workflow invariants.

These tests use hypothesis to generate random inputs and verify that
the workflow maintains key invariants across all execution paths.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from core.workflow import GraphState, SpeculativeGraphRAG
from core.verification_layer import SymbolicVerifier


# ---------------------------------------------------------------------------
# GraphState invariants
# ---------------------------------------------------------------------------

class TestGraphStateInvariants:

    @given(
        patient_note=st.text(min_size=1, max_size=200),
        iteration_count=st.integers(min_value=0, max_value=100),
        backend_key=st.sampled_from(["mock", "ollama", "deepseek_r1", "vllm"]),
        status=st.sampled_from(["valid", "corrected", "escalated", "error"]),
    )
    @settings(max_examples=50, deadline=None)
    def test_graphstate_roundtrip(self, patient_note, iteration_count, backend_key, status):
        state = GraphState(
            patient_note=patient_note,
            iteration_count=iteration_count,
            backend_key=backend_key,
            status=status,
        )
        d = state.to_dict()
        restored = GraphState.from_dict(d)
        assert restored.patient_note == patient_note
        assert restored.iteration_count == iteration_count
        assert restored.backend_key == backend_key
        assert restored.status == status

    @given(
        iterations=st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=1, max_size=10,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_evolve_preserves_history(self, iterations):
        state = GraphState(patient_note="test")
        history = []
        for i in iterations:
            entry = {"iteration": i, "reasoning": f"reasoning_{i}"}
            history.append(entry)
            state = state.evolve(reasoning_history=history)
        assert len(state.reasoning_history) == len(iterations)
        for i, entry in enumerate(state.reasoning_history):
            assert entry["iteration"] == iterations[i]


# ---------------------------------------------------------------------------
# SymbolicVerifier invariants
# ---------------------------------------------------------------------------

class TestSymbolicVerifierInvariants:

    @given(
        path=st.lists(
            st.fixed_dictionaries({
                "head": st.text(min_size=1, max_size=50),
                "relation": st.sampled_from(["INDICATES", "CONTRAINDICATES"]),
                "tail": st.text(min_size=1, max_size=50),
                "confidence": st.floats(min_value=0.0, max_value=1.0),
            }),
            max_size=20,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_verify_result_has_required_fields(self, path):
        verifier = SymbolicVerifier()
        result = verifier.validate(path)
        assert "is_valid" in result
        assert "valid_edges" in result
        assert "violations" in result
        assert "total_checked" in result
        assert "confidence_decay" in result
        assert result["total_checked"] == len(path)
        assert 0.0 <= result["confidence_decay"] <= 1.0

    @given(
        path=st.lists(
            st.fixed_dictionaries({
                "head": st.text(min_size=1, max_size=50),
                "relation": st.just("CONTRAINDICATES"),
                "tail": st.text(min_size=1, max_size=50),
                "confidence": st.floats(min_value=0.0, max_value=1.0),
            }),
            min_size=1, max_size=5,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_confidence_decay_decreases_with_violations(self, path):
        verifier = SymbolicVerifier()
        result = verifier.validate(path, patient_context={})
        if result["violations"]:
            assert result["confidence_decay"] < 1.0


# ---------------------------------------------------------------------------
# Workflow routing invariants
# ---------------------------------------------------------------------------

class TestRoutingInvariants:

    def test_decision_valid_routes_to_synthesize(self):
        """If decision is 'valid', _route returns 'synthesize'."""
        rag = SpeculativeGraphRAG()
        state = GraphState(
            validation_result={"decision": "valid"},
            iteration_count=1,
        )
        assert rag._route(state) == "synthesize"

    def test_decision_correct_under_limit_routes_to_correct(self):
        """If decision is 'correct' and iteration < max, route to 'correct_differential'."""
        rag = SpeculativeGraphRAG(max_iterations=3)
        state = GraphState(
            validation_result={"decision": "correct"},
            iteration_count=1,
        )
        assert rag._route(state) == "correct_differential"

    def test_decision_escalate_routes_to_escalate(self):
        """If decision is 'escalate', route to 'escalate' regardless of iteration."""
        rag = SpeculativeGraphRAG(max_iterations=3)
        state = GraphState(
            validation_result={"decision": "escalate"},
            iteration_count=1,
        )
        assert rag._route(state) == "escalate"

    def test_decision_correct_at_limit_routes_to_escalate(self):
        """If decision is 'correct' and iteration >= max, route to 'escalate'."""
        rag = SpeculativeGraphRAG(max_iterations=3)
        state = GraphState(
            validation_result={"decision": "correct"},
            iteration_count=3,
        )
        assert rag._route(state) == "escalate"

    def test_converged_path_escalates_from_correct(self):
        """Convergence is detected in _correct_differential, not in routing.
        _route_after_correction only escalates when status is already 'escalated'
        (set by convergence check in _correct_differential) or iteration limit reached."""
        rag = SpeculativeGraphRAG(max_iterations=3)
        state = GraphState(
            status="escalated",  # convergence check in _correct_differential set this
            safety_result={"is_safe": False, "violations": [{"reason": "test"}]},
            iteration_count=1,
            proposed_path=[{"head": "A", "relation": "INDICATES", "tail": "B"}],
            prior_reasoning_path=[{"head": "A", "relation": "INDICATES", "tail": "B"}],
        )
        assert rag._route_after_correction(state) == "escalate"

    def test_non_converged_path_continues(self):
        """If status is not escalated and under iteration limit, continue to assess."""
        rag = SpeculativeGraphRAG(max_iterations=3)
        state = GraphState(
            status="valid",
            safety_result={"is_safe": False, "violations": [{"reason": "test"}]},
            iteration_count=1,
            proposed_path=[{"head": "A", "relation": "INDICATES", "tail": "B"}],
            prior_reasoning_path=[],
        )
        assert rag._route_after_correction(state) == "assess_differential"


# ---------------------------------------------------------------------------
# BackendRouter invariants
# ---------------------------------------------------------------------------

class TestBackendRouterInvariants:

    def test_missing_backend_falls_back_to_default(self):
        from core.backend_router import BackendRouter
        from core.llm_backend import MockLLMBackend
        router = BackendRouter({"mock": MockLLMBackend()}, default="mock")
        backend = router.get_backend("nonexistent")
        assert backend.backend_type == "mock"

    def test_no_backend_returns_mock(self):
        from core.backend_router import BackendRouter
        from core.llm_backend import MockLLMBackend
        router = BackendRouter({"mock": MockLLMBackend()}, default="mock")
        backend = router.get_backend(None)
        assert backend.backend_type == "mock"


# ---------------------------------------------------------------------------
# CircuitBreaker invariants
# ---------------------------------------------------------------------------

class TestCircuitBreakerInvariants:

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState

        async def failing_coro():
            raise ValueError("fail")

        breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60.0)
        calls_before_open = 0
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failing_coro)
            calls_before_open += 1
        assert breaker.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_coro)

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        call_count = 0

        async def unstable_coro():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("fail")
            return "ok"

        breaker = CircuitBreaker(name="test2", failure_threshold=3, recovery_timeout=1.0)
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(unstable_coro)
        # Need to wait for recovery_timeout to enter half-open
        import time
        time.sleep(1.1)
        result = await breaker.call(unstable_coro)
        assert result == "ok"
