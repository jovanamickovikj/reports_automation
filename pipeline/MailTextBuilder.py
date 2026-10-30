"""Builds the text of the automatic mail (wording agreed with the business, Macedonian in Latin letters)."""


class MailTextBuilder:

    def build_mail_text(self, activity_date, churn, suspensions, sms, ivr) -> str:
        """
        Returns the whole mail as one string. suspensions and ivr are the numbers to show: before the
        postponement (pre-final mail) or after it (final mail). Churn (churn=None) is written as 'Churn – nema'.
        """
        items = []

        if churn is None:
            items.append("Churn – nema")
        else:
            bans = churn["residential"].bans + churn["business"].bans
            msisdns = churn["residential"].msisdns + churn["business"].msisdns
            parts = [f"Churn – BAN {bans} / MSISDN {msisdns}",
                     self.describe_groups(churn["residential"], churn["business"])]
            items.append(" – ".join(part for part in parts if part))

        total = suspensions["total"]
        parts = [f"Za suspenzija – BAN {total.bans} / MSISDN {total.msisdns}",
                 self.describe_groups(suspensions["residential"], suspensions["business"])]
        items.append(" – ".join(part for part in parts if part))

        sms_total = sms["residential_bans"] + sms["business_bans"]
        items.append(f"SMS Notification – BAN {sms_total} – PRI ({sms['residential_bans']}) BUS ({sms['business_bans']})")

        active, suspended = ivr["active"], ivr["suspended"]
        items.append(
            f"IVR – BAN {active.bans + suspended.bans} / MSISDN {active.msisdns + suspended.msisdns} "
            f"– site se PRI korisnici ({active.bans} ban-a – {active.msisdns} msisdn-a active korisnici i "
            f"{suspended.bans} ban-a – {suspended.msisdns} msisdn-a za suspendirani korisnici)"
        )

        lines = [f"Zakazani aktivnosti za {activity_date:%d.%m.%Y} se sledni:", ""]
        lines += [f"{number}. {item}" for number, item in enumerate(items, start=1)]
        return "\n".join(lines) + "\n"

    @staticmethod
    def describe_groups(residential, business) -> str:
        """'site se PRI' / 'site se BUS' / 'PRI (...), BUS (...)' (empty when there is nobody)."""
        if residential.bans + business.bans == 0:
            return ""
        if business.bans == 0:
            return "site se PRI"
        if residential.bans == 0:
            return "site se BUS"
        return (f"PRI (BAN {residential.bans} / MSISDN {residential.msisdns}), "
                f"BUS (BAN {business.bans} / MSISDN {business.msisdns})")
