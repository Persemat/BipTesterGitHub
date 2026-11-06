import logging
from datetime import datetime, timedelta
import operator as py_operator

logger = logging.getLogger(__name__)

NULL_OPERATORS = ["IS_NULL", "IS_EMPTY", "NULL"]
NOT_NULL_OPERATORS = ["IS_NOT_NULL", "HAS_A_VALUE", "NOT_NULL"]
EQUAL_OPERATORS = ["EQUAL", "IS"]
NOT_EQUAL_OPERATORS = ["NOT_EQUAL", "IS_NOT"]
ORDERING_OPERATORS = {
    "GREATER_THAN": py_operator.gt,
    "GREATER_OR_EQUAL": py_operator.ge,
    "LESS_THAN": py_operator.lt,
    "LESS_OR_EQUAL": py_operator.le,
}
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]

def solve_constraints(operator, target_value, data_type="TEXT", mock_value = "Generic_Value"):
    """
    Resolves the Infobip operator by generating a value that satisfies the condition.
    SUpports TEXT, PHONE NUMBER, NUMBER, BOOLEAN and DATE data types.
    """

    data_type = str(data_type).upper().strip()

    # 1. Nullity states (common to all datatypes)

    if operator in NULL_OPERATORS:
        return ""

    if operator in NOT_NULL_OPERATORS:
        return mock_value

    if target_value is None:
        return mock_value

    val_str = str(target_value).strip()

    # 2. BOOLEAN data type logic
    # EQUAL and NOT EQUAL 
    if data_type == "BOOLEAN":
        target_bool = str(target_value).lower() in ["true", "1", "yes"]
        if operator == "EQUAL":
            return "true" if target_bool else "false"
        elif operator == "NOT_EQUAL":
            return "false" if target_bool else "true"
        return str(target_value).lower()

    # 3. DATE

    if data_type == "DATE":
        parsed_date = None
        date_format = "%Y-%m-%d"
        val_str = str(target_value).strip()

        # Infobip UI uses DD/MM/YYYY, while internal JSON may use YYYY-MM-DD
        for fmt in ["%d/%m/%Y", "%Y-%m-%d"]:
            try:
                parsed_date = datetime.strptime(val_str[:10], fmt)
                date_format = fmt
                break
            except ValueError:
                continue

        # TimeDelta adjustments based on the operator to ensure the generated date satisfies the constraint
        if parsed_date:
            if operator == "EQUAL":
                return parsed_date.strftime(date_format)
            elif operator == "NOT_EQUAL":
                return (parsed_date + timedelta(days=1)).strftime(date_format)
            elif operator == "GREATER_THAN":
                return (parsed_date + timedelta(days=1)).strftime(date_format)
            elif operator == "GREATER_OR_EQUAL":
                return parsed_date.strftime(date_format)
            elif operator == "LESS_THAN":
                return (parsed_date - timedelta(days=1)).strftime(date_format)
            elif operator == "LESS_OR_EQUAL":
                return parsed_date.strftime(date_format)

        return str(target_value)

    # 4. Mathematical logic for NUMBER data type

    if data_type in ["NUMBER","DECIMAL"]:
        try:
            # Cast to float if a decimal point is present, otherwise integer
            val = float(target_value) if "." in str(target_value) else int(target_value)

            # Determine the minimum step to add or subtract for matching the constraint
            step = 1 if isinstance(val,int) else 0.1

            if operator == "EQUAL":
                return str(val)
            elif operator == "NOT_EQUAL":
                return str(val + step)
            elif operator == "GREATER_THAN":
                return str(val + step)
            elif operator == "GREATER_OR_EQUAL":
                return str(val) # Equality satisfies the condition
            elif operator == "LESS_THAN":
                return str(val - step)
            elif operator == "LESS_OR_EQUAL":
                return str(val) # Equality satisfies the condition
                
        except ValueError:
            # Silent fallback to text logic if mathematical casting fails
            pass

    # 5. PHONE NUMBER type
    # Must only contain numeric digits to avoid channel validation failures
    
    if data_type == "PHONE_NUMBER":
        val_str = str(target_value).strip()
        if operator == "EQUAL":
            return val_str
        elif operator == "NOT_EQUAL":
            # Modify the last digit to keep it a valid numeric phone string
            last_digit = val_str[-1] if val_str and val_str[-1].isdigit() else "0"
            replacement = "9" if last_digit != "9" else "8"
            return val_str[:-1] + replacement
        elif operator == "CONTAINS":
            return val_str
        elif operator == "STARTS_WITH":
            return f"{val_str}999"
        elif operator == "ENDS_WITH":
            prefix = "+39" if not val_str.startswith("+") else ""
            return f"{prefix}123{val_str}"
    
    # 6. EMAIL (Validated using email address validator)
    
    if data_type == "EMAIL":
        if "@" in val_str:
            user_part, domain_part = val_str.split("@", 1)
        else:
            user_part, domain_part = "test_user", "example.com"

        if operator in ["IS", "EQUAL", "CONTAINS"]:
            return f"{user_part}@{domain_part}"
        elif operator in ["IS_NOT", "NOT_EQUAL"]:
            return f"{user_part}_different@{domain_part}"
        elif operator == "STARTS_WITH":
            return f"{user_part}suffix@{domain_part}"
        elif operator == "ENDS_WITH":
            # If it must end with domain_part
            return f"custom_{user_part}@{domain_part}"

    # 7. URL (Rules: Validated using URL validator)

    if data_type == "URL":
        base_url = val_str if val_str.startswith("http") else f"https://{val_str}"
        if operator in ["IS", "EQUAL"]:
            return base_url
        elif operator in ["IS_NOT", "NOT_EQUAL"]:
            # Keep it a valid URL format but pointing to a distinct resource
            return f"{base_url.rstrip('/')}/different"


    # 8. LOCATION (Rules: Accepts latitude and longitude)
    
    if "LOCATION" in data_type:
        if operator in ["IS", "EQUAL"]:
            return val_str
        elif operator in ["IS_NOT", "NOT_EQUAL"]:
            return "41.9028,12.4964" # Rome coordinates as a valid different alternative
    
    #  TEXT attributes
    
    if operator == "EQUAL":
        return str(target_value)
        
    elif operator == "NOT_EQUAL":
        # Append a suffix to ensure the string is strictly different
        return f"{target_value}_different"
        
    elif operator == "CONTAINS":
        # Providing the exact target string guarantees it contains it
        return str(target_value)
        
    elif operator == "STARTS_WITH":
        # Append a generic suffix
        return f"{target_value}_suffix"
        
    elif operator == "ENDS_WITH":
        # Prepend a generic prefix
        return f"prefix_{target_value}"

    # Safety fallback for unrecognized operators
    return str(target_value)


    # ---------------------------------------------------------------------------
# Several conditions on the same attribute
#
# solve_constraints() satisfies ONE condition. When a logic tree (AND) or a path
# (two consecutive EVALUATE_ATTRIBUTE nodes) constrains the same attribute more than
# once, the generated value must satisfy all of them at once: e.g. x > 5 AND x < 10.
# ---------------------------------------------------------------------------


def _parse_date(value):
    """Parses a date written either as DD/MM/YYYY or YYYY-MM-DD; returns (date, format) or (None, None)."""
    text = str(value).strip()[:10]
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format), date_format
        except ValueError:
            continue
    return None, None


def _as_comparable_pair(candidate, target_value, data_type):
    """Converts both sides to numbers or dates when the data type calls for it; None if impossible."""
    try:
        if data_type == "DATE":
            candidate_date, _ = _parse_date(candidate)
            target_date, _ = _parse_date(target_value)
            if candidate_date is None or target_date is None:
                return None
            return candidate_date, target_date
        return float(str(candidate).strip()), float(str(target_value).strip())
    except ValueError:
        # Not numeric: ordering operators on plain text fall back to string comparison
        return str(candidate), str(target_value)


def _is_same_value(candidate, target_value, data_type):
    if data_type == "BOOLEAN":
        truthy = ["true", "1", "yes"]
        return (str(candidate).lower() in truthy) == (str(target_value).lower() in truthy)
    if data_type in ["NUMBER", "DECIMAL", "DATE"]:
        pair = _as_comparable_pair(candidate, target_value, data_type)
        return pair is not None and pair[0] == pair[1]
    return str(candidate) == str(target_value)


def satisfies(operator, target_value, candidate, data_type="TEXT"):
    """
    Checks whether `candidate` satisfies "<attribute> <operator> <target_value>".
    Operators the solver does not know are reported as satisfied: there is nothing to verify.
    """
    data_type = normalize_data_type(data_type).upper()
    candidate_text = "" if candidate is None else str(candidate)

    if operator in NULL_OPERATORS:
        return candidate_text == ""
    if operator in NOT_NULL_OPERATORS:
        return candidate_text != ""
    if target_value is None:
        return True

    if operator in ORDERING_OPERATORS:
        pair = _as_comparable_pair(candidate_text, target_value, data_type)
        return pair is not None and ORDERING_OPERATORS[operator](pair[0], pair[1])
    if operator in EQUAL_OPERATORS:
        return _is_same_value(candidate_text, target_value, data_type)
    if operator in NOT_EQUAL_OPERATORS:
        return not _is_same_value(candidate_text, target_value, data_type)

    target_text = str(target_value)
    if operator == "CONTAINS":
        return target_text in candidate_text
    if operator == "STARTS_WITH":
        return candidate_text.startswith(target_text)
    if operator == "ENDS_WITH":
        return candidate_text.endswith(target_text)
    return True


def _neighbour_values(value, data_type):
    """Values right next to `value` (+/- one step); they let a bound sit strictly inside a range."""
    if data_type in ["NUMBER", "DECIMAL"]:
        try:
            number = float(str(value))
        except ValueError:
            return []
        step = 1 if float(number).is_integer() else 0.1
        return [format_number(number - step), format_number(number + step)]
    if data_type == "DATE":
        parsed, date_format = _parse_date(value)
        if parsed is None:
            return []
        return [(parsed + timedelta(days=delta)).strftime(date_format) for delta in (-1, 1)]
    return []


def format_number(number):
    """Renders a float the way solve_constraints does: integers without decimals."""
    return str(int(number)) if float(number).is_integer() else str(round(number, 10))


def _candidate_values(conditions, data_type, mock_value):
    solved = [solve_constraints(op, target, data_type, mock_value) for op, target in conditions]
    candidates = list(solved) + [mock_value]
    for value in solved:
        candidates.extend(_neighbour_values(value, data_type))
    # Text operators such as STARTS_WITH + ENDS_WITH are satisfied by gluing the solutions together
    unique_solved = list(dict.fromkeys(str(value) for value in solved))
    candidates.append("".join(unique_solved))
    candidates.append("".join(reversed(unique_solved)))
    return list(dict.fromkeys(str(candidate) for candidate in candidates))


def solve_conjunction(conditions, data_type="TEXT", mock_value="Generic_Value"):
    """
    Generates one value satisfying ALL the (operator, target_value) conditions of an attribute.

    With a single condition this is exactly solve_constraints(). With several, candidates are
    generated and the first one that passes every check is returned. If no candidate does,
    the conditions are contradictory (or beyond the solver): a warning is logged and the
    value solving the last condition is returned, which is what the old "last one wins"
    merge did.
    """
    if not conditions:
        return mock_value

    if len(conditions) == 1:
        operator, target_value = conditions[0]
        return solve_constraints(operator, target_value, data_type, mock_value)

    normalized_type = normalize_data_type(data_type).upper()
    for candidate in _candidate_values(conditions, data_type, mock_value):
        if all(satisfies(op, target, candidate, normalized_type) for op, target in conditions):
            return candidate

    logger.warning("No single value satisfies all of %s for type %s; using the last condition.", conditions, normalized_type)
    last_operator, last_target = conditions[-1]
    return solve_constraints(last_operator, last_target, data_type, mock_value)
