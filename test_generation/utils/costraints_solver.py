from datetime import datetime, timedelta

def solve_constraints(operator, target_value, data_type="TEXT", mock_value = "Generic_Value"):
    """
    Resolves the Infobip operator by generating a value that satisfies the condition.
    SUpports TEXT, PHONE NUMBER, NUMBER, BOOLEAN and DATE data types.
    """

    data_type = str(data_type).upper().strip()

    # 1. Nullity states (common to all datatypes)

    if operator in ["IS_NULL", "IS_EMPTY"]:
        return ""

    if operator in ["IS_NOT_NULL", "HAS_A_VALUE"]:
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