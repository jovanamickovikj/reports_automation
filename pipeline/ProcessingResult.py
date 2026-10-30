"""What the processing step hands over to the saving and mailing steps."""
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class ProcessingResult:
    report_date: date                 # the date in the title of the report (today)
    activity_date: date               # the day the activities are scheduled for
    new_date: date                    # the day the postponed customers move to
    mail_pre_final_text: str          # all counted activities, WITHOUT the postponements
    mail_final_text: str              # the numbers AFTER the postponements
    suspensions_msisdns_before: int   # S3 MSISDNs before the postponement (decides if the bulk mail is sent)
    suspensions_msisdns_after: int    # S3 MSISDNs left after the postponement (number in the bulk mail)
    suspensions_postponed: pd.DataFrame
    ivr_postponed: pd.DataFrame
    business_customers: pd.DataFrame  # the business customers with S3 on new_date (for Business_korisnici.xlsx)
