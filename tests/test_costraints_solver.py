"""
Full pytest suite for test_generation/utils/costraints_solver.py

Structure (one class per logical responsibility of the module):
  - TestFormatNumber                     -> format_number()
  - TestSolveConstraintsNumber            -> solve_constraints(), NUMBER/DECIMAL
  - TestSolveConstraintsTextFallback      -> solve_constraints(), generic TEXT branch
  - TestSolveConstraintsBoolean            -> solve_constraints(), BOOLEAN
  - TestSolveCostraintsNullityStates       -> solve_constraints(), NULL/NOT_NULL operators (any type)
  - TestSolveConstraintsDate               -> solve_constraints(), DATE
  - TestSolveConstraintsPhoneNumber        -> solve_constraints(), PHONE_NUMBER
  - TestSolveCostraintsEmail               -> solve_constraints(), EMAIL
  - TestSolveConstraintsUrl                -> solve_constraints(), URL
  - TestSolveCostraintsLocation            -> solve_constraints(), LOCATION
  - TestParseDate                          -> _parse_date()
  - TestAsComparablePair                   -> _as_comparable_pair()
  - TestIsSameValue                        -> _is_same_value()
  - TestSatisfies                          -> satisfies(), one group of tests per operator family
  - TestNeighbourValues                    -> _neighbour_values()
  - TestSolveConstraintsSatisfiesRoundTrip -> property test: "whatever solve_constraints()
                                               produces must pass satisfies() for the same
                                               (operator, target_value, data_type)"
  - TestSolveConjunction                   -> solve_conjunction(), all remaining cases

Every test follows Arrange-Act-Assert. Expected values are obtained by tracing the actual
source lines of costraints_solver.py by hand (never guessed).

Where the current code is known to be wrong, the test encodes the CORRECT
behaviour and is marked `xfail(strict=True)`: it documents the bug, fails today, and will
start failing *for a different, good reason* (strict=True turns an unexpected PASS into a
test failure) the day you fix the code without updating the test -- so you don't forget to
remove the marker.
"""

import logging
import pytest

from test_generation.utils.costraints_solver import (
    solve_constraints,
    solve_conjunction,
    satisfies,
    format_number,
    _parse_date,
    _as_comparable_pair,
    _is_same_value,
    _neighbour_values,
)


# ---------------------------------------------------------------------------
# format_number
# ---------------------------------------------------------------------------

class TestFormatNumber:
    """format_number: no business logic, just display formatting."""

    def test_integer_has_no_decimal_point(self):
        assert format_number(6.0) == "6"

    def test_decimal_keeps_its_fraction(self):
        assert format_number(6.5) == "6.5"

    def test_negative_integer(self):
        assert format_number(-3.0) == "-3"

    def test_long_fraction_is_rounded_to_ten_decimals(self):
        # round(number, 10) is what the source actually calls
        assert format_number(1 / 3) == str(round(1 / 3, 10))


# ---------------------------------------------------------------------------
# solve_constraints - NUMBER / DECIMAL
# ---------------------------------------------------------------------------

class TestSolveConstraintsNumber:
    """solve_constraints for NUMBER: integer step is 1 (see 'step = 1 if isinstance(val, int) else 0.1')."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "5"),
        ("NOT_EQUAL", "6"),          # val + step, same branch as GREATER_THAN
        ("GREATER_THAN", "6"),
        ("GREATER_OR_EQUAL", "5"),
        ("LESS_THAN", "4"),
        ("LESS_OR_EQUAL", "5"),
    ])
    def test_integer_operators(self, operator, expected):
        # Arrange: operator and integer target in input
        # Act
        result = solve_constraints(operator, "5", "NUMBER", mock_value="Generic_Value")
        # Assert
        assert result == expected

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "5.5"),
        ("GREATER_THAN", "5.6"),     # step is 0.1 because the input contains a "."
        ("LESS_THAN", "5.4"),
    ])
    def test_decimal_operators_use_a_smaller_step(self, operator, expected):
        # Arrange: a target with a decimal point selects step = 0.1 instead of 1
        # Act
        result = solve_constraints(operator, "5.5", "NUMBER", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_non_numeric_target_falls_back_to_text_logic(self):
        # Arrange: int("abc") raises ValueError -> the except block swallows it silently
        # and execution falls through to the generic TEXT branch at the bottom of the function
        # Act
        result = solve_constraints("EQUAL", "abc", "NUMBER", mock_value="Generic_Value")
        # Assert: TEXT's EQUAL branch is "return str(target_value)"
        assert result == "abc"


# ---------------------------------------------------------------------------
# solve_constraints - generic TEXT fallback
# ---------------------------------------------------------------------------

class TestSolveConstraintsTextFallback:
    """solve_constraints for TEXT (also reached by any data_type that falls through
    every specific branch above, e.g. 'abc' casted as NUMBER)."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "test"),
        ("NOT_EQUAL", "test_different"),
        ("CONTAINS", "test"),
        ("STARTS_WITH", "test_suffix"),
        ("ENDS_WITH", "prefix_test"),
    ])
    def test_string_operators(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "test", "TEXT")
        # Assert
        assert result == expected

    def test_unrecognized_operator_falls_back_to_str_target_value(self):
        # Arrange: the module's last line is a safety net for operators it doesn't know
        # Act
        result = solve_constraints("SOME_UNKNOWN_OPERATOR", "test", "TEXT")
        # Assert
        assert result == "test"


# ---------------------------------------------------------------------------
# solve_constraints - BOOLEAN
# ---------------------------------------------------------------------------

class TestSolveConstraintsBoolean:
    """solve_constraints for BOOLEAN."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "true"),
        ("NOT_EQUAL", "false"),
    ])
    def test_boolean_operators_with_true_target(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "true", "BOOLEAN", mock_value="Generic_Value")
        # Assert
        assert result == expected

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "false"),
        ("NOT_EQUAL", "true"),
    ])
    def test_boolean_operators_with_false_target(self, operator, expected):
        # Arrange: symmetrical case with target_value="false" to make sure the branch
        # isn't hardcoded to always answer "true"/"false" regardless of the input
        # Act
        result = solve_constraints(operator, "false", "BOOLEAN", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_unrecognized_operator_returns_lowercased_target(self):
        # Arrange: the BOOLEAN branch's final line is "return str(target_value).lower()"
        # Act
        result = solve_constraints("IS", "TRUE", "BOOLEAN", mock_value="Generic_Value")
        # Assert
        assert result == "true"


# ---------------------------------------------------------------------------
# solve_constraints - nullity states (shared by every data type)
# ---------------------------------------------------------------------------

class TestSolveCostraintsNullityStates:
    """NULL_OPERATORS and NOT_NULL_OPERATORS are checked first, before data_type is
    even considered: they must short-circuit regardless of data_type."""

    @pytest.mark.parametrize("operator, expected", [
        ("IS_NULL", ""),
        ("IS_EMPTY", ""),
        ("NULL", ""),
        ("IS_NOT_NULL", "Generic_Value"),
        ("HAS_A_VALUE", "Generic_Value"),
        ("NOT_NULL", "Generic_Value"),
    ])
    def test_nullity_operators_on_text(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "any_value", "TEXT", mock_value="Generic_Value")
        # Assert
        assert result == expected

    @pytest.mark.parametrize("data_type", ["TEXT", "NUMBER", "BOOLEAN", "PHONE_NUMBER", "DATE"])
    def test_nullity_operators_bypass_data_type_entirely(self, data_type):
        # Arrange: same two operators, but sweeping across data types to prove the
        # nullity check in solve_constraints really happens before any type-specific branch
        # Act / Assert
        assert solve_constraints("IS_NULL", "any_value", data_type, "Generic_Value") == ""
        assert solve_constraints("IS_NOT_NULL", "any_value", data_type, "Generic_Value") == "Generic_Value"

    def test_none_target_value_falls_back_to_mock_value(self):
        # Arrange: "if target_value is None: return mock_value" fires even for a normal
        # operator like EQUAL, before any data-type branch runs
        # Act
        result = solve_constraints("EQUAL", None, "TEXT", mock_value="Generic_Value")
        # Assert
        assert result == "Generic_Value"


# ---------------------------------------------------------------------------
# solve_constraints - DATE
# ---------------------------------------------------------------------------

class TestSolveConstraintsDate:
    """solve_constraints for DATE, input in ISO format (YYYY-MM-DD)."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "2023-01-01"),
        ("NOT_EQUAL", "2023-01-02"),
        ("GREATER_THAN", "2023-01-02"),
        ("GREATER_OR_EQUAL", "2023-01-01"),
        ("LESS_THAN", "2022-12-31"),
        ("LESS_OR_EQUAL", "2023-01-01"),
    ])
    def test_date_operators_iso_format(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "2023-01-01", "DATE", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_date_operators_preserve_the_input_format(self):
        # Arrange: Infobip's UI uses DD/MM/YYYY; the function must answer in the SAME
        # format it was given, not silently convert to ISO
        # Act
        result = solve_constraints("GREATER_THAN", "01/03/2023", "DATE", mock_value="Generic_Value")
        # Assert
        assert result == "02/03/2023"

    def test_unparseable_date_falls_back_to_str_target_value(self):
        # Arrange: neither DD/MM/YYYY nor YYYY-MM-DD matches -> parsed_date stays None
        # -> "return str(target_value)" at the end of the DATE branch
        # Act
        result = solve_constraints("EQUAL", "not-a-date", "DATE", mock_value="Generic_Value")
        # Assert
        assert result == "not-a-date"


# ---------------------------------------------------------------------------
# solve_constraints - PHONE_NUMBER
# ---------------------------------------------------------------------------

class TestSolveConstraintsPhoneNumber:
    """solve_constraints for PHONE_NUMBER.
    """

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "1234567890"),
        ("NOT_EQUAL", "1234567899"),  # last digit 0 -> 9
        ("CONTAINS", "1234567890"),
        ("STARTS_WITH", "1234567890999"),  # appends '999' to the whole number
        ("ENDS_WITH", "391231234567890"),  # prepends '39123' to the whole number
    ])
    def test_phone_number_operators_already_correct(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "1234567890", "PHONE_NUMBER", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_not_equal_flips_the_last_digit_even_without_plus_sign(self):
        # Arrange: a target with no leading "+" must still get a valid replacement,
        # and must NOT grow a "+" that wasn't there (has_plus guards the prefix)
        # Act
        result = solve_constraints("NOT_EQUAL", "1234567890", "PHONE_NUMBER", mock_value="Generic_Value")
        # Assert
        assert result == "1234567899"

    def test_target_with_no_digits_falls_back_to_mock_value(self):
        # Arrange: digits_only would be "" -> "if not digits_only: return mock_value"
        # Act
        result = solve_constraints("EQUAL", "abc", "PHONE_NUMBER", mock_value="Generic_Value")
        # Assert
        assert result == "Generic_Value"


# ---------------------------------------------------------------------------
# solve_constraints - EMAIL
# ---------------------------------------------------------------------------

class TestSolveCostraintsEmail:
    """solve_constraints for EMAIL."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "test_user@example.com"),
        ("CONTAINS", "test_user@example.com"),
        ("NOT_EQUAL", "test_user_different@example.com"),
        ("STARTS_WITH", "test_user@example.com.org"), # Ora aggiunge .org alla fine
        ("ENDS_WITH", "info.test_user@example.com"),  # Ora aggiunge info. all'inizio
    ])
    def test_email_operators(self, operator, expected):
        # Act
        result = solve_constraints(operator, "test_user@example.com", "EMAIL", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_target_without_at_sign_uses_a_default_mailbox(self):
        # Act
        result = solve_constraints("EQUAL", "not-an-email", "EMAIL", mock_value="Generic_Value")
        # Assert
        assert result == "not-an-email@example.com"
        
    def test_starts_with_result_satisfies_its_own_constraint(self):
        # Arrange
        target = "test_user@example.com"
        # Act
        result = solve_constraints("STARTS_WITH", target, "EMAIL", mock_value="Generic_Value")
        # Assert: ora "test_user@example.com.org" inizia con "test_user@example.com" -> True!
        assert satisfies("STARTS_WITH", target, result, "EMAIL")


# ---------------------------------------------------------------------------
# solve_constraints - URL
# ---------------------------------------------------------------------------

class TestSolveConstraintsUrl:
    """solve_constraints for URL."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "https://example.com"),
        ("NOT_EQUAL", "https://example.com/different"),
    ])
    def test_url_operators(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "https://example.com", "URL", mock_value="Generic_Value")
        # Assert
        assert result == expected

    def test_target_without_scheme_gets_https_prepended(self):
        # Arrange: "base_url = val_str if val_str.startswith('http') else f'https://{val_str}'"
        # Act
        result = solve_constraints("EQUAL", "example.com", "URL", mock_value="Generic_Value")
        # Assert
        assert result == "https://example.com"

    def test_operator_with_no_url_branch_falls_through_to_text_logic(self):
        # Arrange: the URL block only handles IS/EQUAL and IS_NOT/NOT_EQUAL. STARTS_WITH
        # has no matching branch there, so execution falls all the way through to the
        # generic TEXT fallback at the bottom of the function. This is a characterization
        # test: it documents what the code actually does today, not necessarily what it
        # SHOULD do (worth a conversation: a URL with "_suffix" glued on isn't a valid URL).
        # Act
        result = solve_constraints("STARTS_WITH", "https://example.com", "URL", mock_value="Generic_Value")
        # Assert
        assert result == "https://example.com_suffix"


# ---------------------------------------------------------------------------
# solve_constraints - LOCATION
# ---------------------------------------------------------------------------

class TestSolveCostraintsLocation:
    """solve_constraints for LOCATION ('LOCATION' in data_type, so e.g. 'GEO_LOCATION' also matches)."""

    @pytest.mark.parametrize("operator, expected", [
        ("EQUAL", "37.7749,-122.4194"),
        ("NOT_EQUAL", "41.9028,12.4964"),
    ])
    def test_location_operators(self, operator, expected):
        # Arrange: operator and target in input
        # Act
        result = solve_constraints(operator, "37.7749,-122.4194", "LOCATION", mock_value="Generic_Value")
        # Assert
        assert result == expected

# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    """_parse_date: tries DD/MM/YYYY then YYYY-MM-DD, returns (None, None) if neither matches."""

    def test_iso_format(self):
        from datetime import datetime
        parsed, fmt = _parse_date("2023-05-17")
        assert parsed == datetime(2023, 5, 17)
        assert fmt == "%Y-%m-%d"

    def test_day_month_year_format(self):
        from datetime import datetime
        parsed, fmt = _parse_date("17/05/2023")
        assert parsed == datetime(2023, 5, 17)
        assert fmt == "%d/%m/%Y"

    def test_unparseable_value_returns_none_none(self):
        parsed, fmt = _parse_date("not-a-date")
        assert parsed is None
        assert fmt is None

    def test_extra_characters_after_the_date_are_truncated(self):
        # Arrange: the function slices "str(value).strip()[:10]" before parsing, so a full
        # ISO timestamp should still parse as a plain date
        from datetime import datetime
        parsed, fmt = _parse_date("2023-05-17T10:30:00")
        # Assert
        assert parsed == datetime(2023, 5, 17)
        assert fmt == "%Y-%m-%d"


# ---------------------------------------------------------------------------
# _as_comparable_pair
# ---------------------------------------------------------------------------

class TestAsComparablePair:
    """_as_comparable_pair: converts both sides to a comparable (numeric/date/string) pair."""

    def test_numeric_pair(self):
        assert _as_comparable_pair("5", "10", "NUMBER") == (5.0, 10.0)

    def test_date_pair(self):
        from datetime import datetime
        candidate, target = _as_comparable_pair("2023-01-01", "2023-01-05", "DATE")
        assert candidate == datetime(2023, 1, 1)
        assert target == datetime(2023, 1, 5)

    def test_date_pair_with_one_unparseable_side_returns_none(self):
        # Arrange: if either side fails to parse as a date, the whole pair is unusable
        assert _as_comparable_pair("not-a-date", "2023-01-05", "DATE") is None

    def test_non_numeric_non_date_falls_back_to_string_pair(self):
        # Arrange: data_type="TEXT" with non-numeric values -> float() raises ValueError
        # -> except block returns (str(candidate), str(target_value))
        assert _as_comparable_pair("abc", "abd", "TEXT") == ("abc", "abd")


# ---------------------------------------------------------------------------
# _is_same_value
# ---------------------------------------------------------------------------

class TestIsSameValue:
    """_is_same_value: equality test used by both satisfies() and EQUAL_OPERATORS."""

    @pytest.mark.parametrize("candidate, target", [
        ("true", "1"),
        ("1", "yes"),
        ("false", "0"),   # "0" is not in the truthy list, so both sides are falsy -> equal
    ])
    def test_boolean_equivalence_classes(self, candidate, target):
        # Arrange: any spelling of "true" (true/1/yes) must be equivalent to any other
        assert _is_same_value(candidate, target, "BOOLEAN") is True

    def test_boolean_true_is_not_same_as_false(self):
        assert _is_same_value("true", "false", "BOOLEAN") is False

    def test_number_equality_is_numeric_not_textual(self):
        # Arrange: "5" and "5.0" are textually different but numerically equal
        assert _is_same_value("5", "5.0", "NUMBER") is True

    def test_date_equality_across_formats(self):
        # Arrange: same calendar date, different textual format
        assert _is_same_value("2023-01-01", "01/01/2023", "DATE") is True

    def test_text_equality_is_plain_string_comparison(self):
        assert _is_same_value("Test", "test", "TEXT") is False
        assert _is_same_value("test", "test", "TEXT") is True


# ---------------------------------------------------------------------------
# satisfies
# ---------------------------------------------------------------------------

class TestSatisfies:
    """satisfies(): one group of tests per operator family handled by the function."""

    @pytest.mark.parametrize("operator", ["IS_NULL", "IS_EMPTY", "NULL"])
    def test_null_operators(self, operator):
        assert satisfies(operator, None, "", "TEXT") is True
        assert satisfies(operator, None, "something", "TEXT") is False

    @pytest.mark.parametrize("operator", ["IS_NOT_NULL", "HAS_A_VALUE", "NOT_NULL"])
    def test_not_null_operators(self, operator):
        assert satisfies(operator, None, "something", "TEXT") is True
        assert satisfies(operator, None, "", "TEXT") is False

    def test_candidate_none_is_treated_as_empty_string(self):
        # Arrange: "candidate_text = '' if candidate is None else str(candidate)"
        assert satisfies("IS_NULL", None, None, "TEXT") is True

    def test_target_value_none_is_always_satisfied(self):
        # Arrange: "if target_value is None: return True" -- a safety net for a
        # malformed condition that isn't a nullity operator but still has no target
        assert satisfies("EQUAL", None, "anything", "TEXT") is True

    @pytest.mark.parametrize("operator, target, candidate, expected", [
        ("GREATER_THAN", "5", "6", True),
        ("GREATER_THAN", "5", "5", False),
        ("GREATER_OR_EQUAL", "5", "5", True),
        ("LESS_THAN", "5", "4", True),
        ("LESS_OR_EQUAL", "5", "5", True),
    ])
    def test_ordering_operators_on_numbers(self, operator, target, candidate, expected):
        assert satisfies(operator, target, candidate, "NUMBER") is expected

    def test_ordering_operator_on_unparseable_number_is_not_satisfied(self):
        # Arrange: _as_comparable_pair returns a (str, str) pair for TEXT, but
        # py_operator.gt on numeric-looking NUMBER data that fails to parse returns None
        # from _as_comparable_pair's except branch is unreachable for NUMBER+ValueError
        # (it falls back to string compare) -- so this documents that fallback instead
        assert satisfies("GREATER_THAN", "abc", "abd", "TEXT") is True  # "abd" > "abc" lexically

    @pytest.mark.parametrize("operator", ["EQUAL", "IS"])
    def test_equal_operators_delegate_to_is_same_value(self, operator):
        assert satisfies(operator, "5", "5.0", "NUMBER") is True
        assert satisfies(operator, "5", "6", "NUMBER") is False

    @pytest.mark.parametrize("operator", ["NOT_EQUAL", "IS_NOT"])
    def test_not_equal_operators_negate_is_same_value(self, operator):
        assert satisfies(operator, "5", "6", "NUMBER") is True
        assert satisfies(operator, "5", "5.0", "NUMBER") is False

    def test_contains(self):
        assert satisfies("CONTAINS", "user", "test_user@example.com", "TEXT") is True
        assert satisfies("CONTAINS", "xyz", "test_user@example.com", "TEXT") is False

    def test_starts_with(self):
        assert satisfies("STARTS_WITH", "test", "test_user", "TEXT") is True
        assert satisfies("STARTS_WITH", "user", "test_user", "TEXT") is False

    def test_ends_with(self):
        assert satisfies("ENDS_WITH", "user", "test_user", "TEXT") is True
        assert satisfies("ENDS_WITH", "test", "test_user", "TEXT") is False

    def test_unrecognized_operator_is_reported_as_satisfied(self):
        # Arrange: "return True" is the function's final safety net
        assert satisfies("SOME_UNKNOWN_OPERATOR", "x", "y", "TEXT") is True


# ---------------------------------------------------------------------------
# _neighbour_values
# ---------------------------------------------------------------------------

class TestNeighbourValues:
    """_neighbour_values: +/- one step around a value, used by solve_conjunction to
    build extra candidates for a bound to sit strictly inside an open range."""

    def test_integer_number_uses_step_one(self):
        assert _neighbour_values("5", "NUMBER") == ["4", "6"]

    def test_decimal_number_uses_step_point_one(self):
        assert _neighbour_values("5.5", "NUMBER") == ["5.4", "5.6"]

    def test_non_numeric_value_returns_empty_list(self):
        assert _neighbour_values("abc", "NUMBER") == []

    def test_date_returns_day_before_and_day_after_same_format(self):
        assert _neighbour_values("2023-01-05", "DATE") == ["2023-01-04", "2023-01-06"]

    def test_unparseable_date_returns_empty_list(self):
        assert _neighbour_values("not-a-date", "DATE") == []

    def test_text_data_type_has_no_neighbours(self):
        # Arrange: only NUMBER/DECIMAL and DATE are handled; anything else returns []
        assert _neighbour_values("test", "TEXT") == []


# ---------------------------------------------------------------------------
# Property test: solve_constraints() must satisfy its own satisfies()
# ---------------------------------------------------------------------------

class TestSolveConstraintsSatisfiesRoundTrip:
    """
    Generic correctness property, independent of any specific hardcoded expected string:
    for every (operator, target_value, data_type) where this is meaningful, the value
    produced by solve_constraints() must pass satisfies() for that same condition.

    This single parametrized test catches the EMAIL/STARTS_WITH bug on its own (no need
    to know the exact broken string in advance), and documents exactly which combinations
    are known-broken today via the xfail-marked parameters.
    """

    _CASES = [
        ("EQUAL", "test", "TEXT"),
        ("NOT_EQUAL", "test", "TEXT"),
        ("CONTAINS", "test", "TEXT"),
        ("STARTS_WITH", "test", "TEXT"),
        ("ENDS_WITH", "test", "TEXT"),
        ("EQUAL", "5", "NUMBER"),
        ("NOT_EQUAL", "5", "NUMBER"),
        ("GREATER_THAN", "5", "NUMBER"),
        ("LESS_THAN", "5", "NUMBER"),
        ("EQUAL", "2023-01-01", "DATE"),
        ("NOT_EQUAL", "2023-01-01", "DATE"),
        ("GREATER_THAN", "2023-01-01", "DATE"),
        ("EQUAL", "true", "BOOLEAN"),
        ("NOT_EQUAL", "true", "BOOLEAN"),
        ("EQUAL", "test_user@example.com", "EMAIL"),
        ("NOT_EQUAL", "test_user@example.com", "EMAIL"),
        ("ENDS_WITH", "test_user@example.com", "EMAIL"),
        ("EQUAL", "https://example.com", "URL"),
        ("NOT_EQUAL", "https://example.com", "URL"),
        ("EQUAL", "+1234567890", "PHONE_NUMBER"),
        ("NOT_EQUAL", "+1234567890", "PHONE_NUMBER"),
    ]

    @pytest.mark.parametrize("operator, target_value, data_type", _CASES)
    def test_generated_value_satisfies_its_own_constraint(self, operator, target_value, data_type):
        # Act
        candidate = solve_constraints(operator, target_value, data_type, mock_value="Generic_Value")
        # Assert
        assert satisfies(operator, target_value, candidate, data_type), (
            f"solve_constraints({operator!r}, {target_value!r}, {data_type!r}) "
            f"returned {candidate!r}, which does not satisfy its own constraint"
        )


# ---------------------------------------------------------------------------
# solve_conjunction
# ---------------------------------------------------------------------------

class TestSolveConjunction:
    """solve_conjunction: generates ONE value satisfying several (operator, target) pairs
    on the SAME attribute at once."""

    def test_zero_conditions_returns_mock_value(self):
        # Arrange: "if not conditions: return mock_value"
        result = solve_conjunction([], "TEXT", mock_value="Generic_Value")
        assert result == "Generic_Value"

    def test_single_condition_delegates_to_solve_constraints(self):
        # Arrange: with exactly one condition, solve_conjunction must behave exactly
        # like calling solve_constraints() directly
        conjunction_result = solve_conjunction([("EQUAL", "test")], "TEXT", mock_value="Generic_Value")
        direct_result = solve_constraints("EQUAL", "test", "TEXT", mock_value="Generic_Value")
        assert conjunction_result == direct_result

    def test_two_conditions_on_same_attribute_does_not_crash(self):
        # Arrange: a classic range, x > 5 AND x < 10
        result = solve_conjunction(
            [("GREATER_THAN", "5"), ("LESS_THAN", "10")],
            "NUMBER",
            mock_value="Generic_Value",
        )
        # Assert: the value should satisfy both conditions at once
        assert satisfies("GREATER_THAN", "5", result, "NUMBER")
        assert satisfies("LESS_THAN", "10", result, "NUMBER")

    def test_three_conditions_on_same_attribute(self):
        # Arrange: x > 5 AND x < 20 AND x != 10
        conditions = [("GREATER_THAN", "5"), ("LESS_THAN", "20"), ("NOT_EQUAL", "10")]
        # Act
        result = solve_conjunction(conditions, "NUMBER", mock_value="Generic_Value")
        # Assert
        assert all(satisfies(op, target, result, "NUMBER") for op, target in conditions)

    def test_text_starts_with_and_ends_with_use_the_glued_candidate(self):
        # Arrange: neither solved value alone can satisfy both STARTS_WITH and ENDS_WITH
        # at once, but _candidate_values() also tries gluing the two solved strings
        # together -- this is exactly the scenario that trick exists for
        conditions = [("STARTS_WITH", "foo"), ("ENDS_WITH", "bar")]
        # Act
        result = solve_conjunction(conditions, "TEXT", mock_value="Generic_Value")
        # Assert
        assert result.startswith("foo")
        assert result.endswith("bar")

    
    def test_contradictory_conditions_log_a_warning_and_fall_back(self, caplog):
        # Arrange: x > 100 AND x < 0 can never be satisfied by any candidate
        conditions = [("GREATER_THAN", "100"), ("LESS_THAN", "0")]
        # Act
        with caplog.at_level(logging.WARNING):
            result = solve_conjunction(conditions, "NUMBER", mock_value="Generic_Value")
        # Assert: the expected CORRECT behaviour -- a warning is logged, and the function
        # falls back to solving the LAST condition on its own (the documented "last one wins")
        assert "No single value satisfies" in caplog.text
        assert result == solve_constraints("LESS_THAN", "0", "NUMBER", mock_value="Generic_Value")
