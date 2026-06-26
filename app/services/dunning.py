"""Dunning engine - manages recovery sequences for failed payments."""

# Default dunning sequence (email + SMS campaign)
# Based on Baremetrics data: highest recovery in first 7 days
DUNNING_SEQUENCE = [
    {"step": 1, "day": 0,  "channel": "email", "name": "Same-day notification"},
    {"step": 2, "day": 3,  "channel": "email", "name": "Helpful reminder"},
    {"step": 3, "day": 7,  "channel": "email", "name": "Loss aversion"},
    {"step": 4, "day": 8,  "channel": "sms",   "name": "SMS nudge"},
    {"step": 5, "day": 14, "channel": "email", "name": "Urgency + SMS"},
    {"step": 6, "day": 21, "channel": "email", "name": "Re-engagement + downgrade"},
    {"step": 7, "day": 28, "channel": "email", "name": "Final notice"},
]

DEFAULT_EMAIL_TEMPLATES = {
    1: {
        "subject": "Heads up — we couldn't process your payment",
        "body": """<p>Hi {{customer_name}},</p>
<p>We tried to process your {{plan_name}} subscription payment of <strong>${{amount}}</strong> but it didn't go through.</p>
<p>This is usually just an expired card or a temporary bank hold. You can fix it in one click:</p>
<p><a href="{{update_link}}" style="display:inline-block;padding:12px 24px;background:#4F46E5;color:white;text-decoration:none;border-radius:6px;">
  Update Payment Method
</a></p>
<p>Your service is still active — we'll try again in a few days.</p>
<p>— The {{app_name}} team</p>"""
    },
    3: {
        "subject": "Your {{app_name}} access is at risk",
        "body": """<p>Hi {{customer_name}},</p>
<p>We still haven't been able to process your payment, and your {{plan_name}} access will be paused soon.</p>
<p>You'll lose access to:</p>
<ul>
{% for benefit in plan_benefits %}
  <li>{{ benefit }}</li>
{% endfor %}
</ul>
<p><a href="{{update_link}}" style="display:inline-block;padding:12px 24px;background:#4F46E5;color:white;text-decoration:none;border-radius:6px;">
  Keep My Access — Update Payment
</a></p>
<p>Need help? Just reply to this email.</p>
<p>— The {{app_name}} team</p>"""
    },
    5: {
        "subject": "Final notice — {{app_name}} access ending soon",
        "body": """<p>Hi {{customer_name}},</p>
<p>This is our final attempt to reach you. Your {{plan_name}} subscription will be cancelled in 7 days if we can't process your payment.</p>
<p><a href="{{update_link}}" style="display:inline-block;padding:12px 24px;background:#DC2626;color:white;text-decoration:none;border-radius:6px;">
  Reactivate Now
</a></p>
<p>We'd love to keep you. Reply if you have any questions.</p>
<p>— The {{app_name}} team</p>"""
    },
    7: {
        "subject": "Your {{app_name}} subscription has ended",
        "body": """<p>Hi {{customer_name}},</p>
<p>We weren't able to process your payment and your subscription has ended. We're sad to see you go.</p>
<p>If you'd like to come back, you can reactivate anytime:</p>
<p><a href="{{reactivate_link}}" style="display:inline-block;padding:12px 24px;background:#4F46E5;color:white;text-decoration:none;border-radius:6px;">
  Reactivate My Account
</a></p>
<p>Thanks for being part of {{app_name}}.</p>
<p>— The {{app_name}} team</p>"""
    },
}

DEFAULT_SMS_TEMPLATES = {
    4: "Hi {{customer_name}}, we couldn't process your {{plan_name}} payment (${{amount}}). Update your card here: {{update_link}} — {{app_name}}",
}


def get_sequence_for_failure(failed_payment: dict) -> list[dict]:
    """Return the dunning sequence appropriate for this failure."""
    decline_code = failed_payment.get("decline_code", "")

    # Hard declines: shorter sequence, focus on card update only
    hard_declines = {
        "incorrect_number", "lost_card", "stolen_card", "pickup_card",
        "revocation_of_authorization", "revocation_of_all_authorizations",
        "authentication_required", "highest_risk_level", "transaction_not_allowed",
    }

    if decline_code in hard_declines:
        # For hard declines: shorter sequence, retries won't help
        return [
            {"step": 1, "day": 0, "channel": "email", "name": "Card issue notification"},
            {"step": 2, "day": 3, "channel": "email", "name": "Reminder to update card"},
            {"step": 3, "day": 7, "channel": "sms", "name": "SMS card update request"},
            {"step": 4, "day": 14, "channel": "email", "name": "Final card update request"},
        ]

    # Soft declines: full sequence with retry window
    return DUNNING_SEQUENCE


def determine_decline_category(decline_code: str) -> str:
    """Categorize decline for analytics and segmentation."""
    soft_declines = {
        "insufficient_funds", "do_not_honor", "generic_decline",
        "try_again_later", "no_action_taken", "processing_error",
        "call_issuer", "expired_card", "card_velocity_exceeded",
    }
    card_data_declines = {"expired_card", "invalid_expiry", "invalid_number", "invalid_cvc"}

    if not decline_code:
        return "unknown"
    if decline_code in card_data_declines:
        return "card_data"
    if decline_code in soft_declines:
        return "soft"
    return "hard"
