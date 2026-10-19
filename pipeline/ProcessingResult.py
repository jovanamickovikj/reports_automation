"""What the processing step hands over to the saving and mailing steps."""
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class ProcessingResult:
    activity_date: date               # the day the activities are scheduled for
    new_date: date                    # the day the postponed customers move to
    mail_text: str
    suspensions_postponed: pd.DataFrame
    ivr_postponed: pd.DataFrame
