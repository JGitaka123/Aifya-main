"""Sequential reference numbers shared by the service modules.

Codes such as ``DV-20260101-0007`` or ``OT-003`` carry a sequence number in
their tail. The next number has to start from the highest one already issued,
including rows that were later soft-deleted: those rows still hold their number
in the table's unique key, so counting only the live rows hands back a number
that is already taken and the insert fails outright.
"""

from sqlalchemy import Integer, func


def highest_sequence(column):
    """
    SQL expression for the highest number in a reference-code column.

    The tail of each code is read as a number, so zero-padded codes (``OT-003``)
    and plain ones (``OT-3``) rank together, and a code that does not end in a
    number is ignored instead of breaking the query or the comparison.

    @param column: The code column, for example ClinicalTrial.trial_code
    @returns A scalar SQL expression holding the highest tail number, or NULL
    """
    return func.max(func.cast(func.substring(column, "[0-9]+$"), Integer))
