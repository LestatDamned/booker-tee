def mapping_field_label(value: object) -> str:
    labels = {
        "operation_date": "дата",
        "posting_date": "дата проводки",
        "description": "описание",
        "amount": "сумма",
        "debit_amount": "списание",
        "credit_amount": "зачисление",
        "currency": "валюта",
        "balance_after": "остаток после операции",
    }
    field = "" if value is None else str(value)
    return labels.get(field, field)
