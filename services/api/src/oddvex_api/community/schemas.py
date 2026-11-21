"""Request and response models for the community.

Nothing here carries an email address, a display name, a plan, a user id or tracker
data: other users are identified by handle only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import DataMode, PriceOut, SportsbookRef

HANDLE_MIN = 3
HANDLE_MAX = 20
BIO_MAX = 280
ANALYSIS_MAX = 1000
COMMENT_MAX = 500
REPORT_DETAILS_MAX = 500

PickMarket = Literal["moneyline", "spread", "total"]
PickOutcome = Literal["home", "away", "draw", "over", "under"]
PickStatus = Literal["pending", "graded", "void"]
PickResult = Literal["won", "lost", "push"]
ModerationStatus = Literal["visible", "hidden", "removed"]
ReportTargetType = Literal["pick", "comment", "profile"]
ReportReason = Literal[
    "spam",
    "harassment",
    "inducement_to_bet",
    "misleading_claims",
    "personal_information",
    "other",
]
ReportStatus = Literal["open", "resolved"]
ResolveAction = Literal["dismiss", "hide_content", "remove_content", "suspend_author"]
#: How a report was closed: one of the decisions above, or ``restore_content`` when an
#: administrator restored the content it is about (``POST /v1/admin/community/restore``).
ReportResolution = Literal[
    "dismiss", "hide_content", "remove_content", "suspend_author", "restore_content"
]
FeedScope = Literal["following", "everyone"]
LeaderboardWindow = Literal["30d", "90d", "all"]


# ------------------------------------------------------------------ guidelines
class GuidelineRuleOut(BaseModel):
    key: str
    title: str
    text: str


class CommunityGuidelinesOut(BaseModel):
    version: str = Field(description="Date of the current wording.")
    intro: str
    rules: list[GuidelineRuleOut]
    enforcement: str
    help: str = Field(description="The responsible-gambling line, with the helpline.")


# --------------------------------------------------------------------- record
class WinRateIntervalOut(BaseModel):
    low: float
    high: float
    confidence_level: float = Field(description="0.95: a Wilson 95% interval.")


class CommunityRecordOut(BaseModel):
    """Computed only from graded picks. Every pick is structured, timestamped before
    the event and graded by the server, so the whole record is verified."""

    verified: Literal[True] = True
    picks: int = Field(description="Graded picks: wins + losses + pushes.")
    wins: int
    losses: int
    pushes: int
    win_rate: float | None = Field(
        default=None, description="wins / (wins + losses), as a fraction. Pushes are left out."
    )
    win_rate_interval: WinRateIntervalOut | None = Field(
        default=None, description="Wilson 95% interval of `win_rate`."
    )
    average_price: PriceOut | None = Field(
        default=None, description="Mean decimal price of the graded picks, in every format."
    )
    flat_stake_roi: float | None = Field(
        default=None,
        description=(
            "Units won or lost divided by units staked, at 1 unit per graded pick and "
            "the price recorded when each pick was posted. A fraction."
        ),
    )
    units_profit: float = Field(description="Units won or lost at 1 unit per graded pick.")
    method: str = Field(description="How the numbers above are computed.")
    sample_note: str | None = Field(
        default=None,
        description="Set below 30 graded picks: too few to tell skill from luck.",
    )
    caveat: str = Field(description="Past results do not predict future results.")


# ------------------------------------------------------------------- profiles
class ProfileUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str = Field(
        max_length=64,
        description=(
            "3 to 20 characters: letters a-z, digits and underscores. Upper-case letters "
            "are lowered, so a handle is unique whatever the case."
        ),
        examples=["demo_bettor"],
    )
    bio: str | None = Field(default=None, max_length=BIO_MAX, description="Plain text. No links.")
    is_public: bool = Field(
        description="Only a public profile can post picks and comments and be found."
    )


class ProfileOut(BaseModel):
    """A public profile. Never contains an email, a name, a plan or tracker data."""

    handle: str
    bio: str | None = None
    joined: str = Field(description="Month the profile was created, `YYYY-MM`.")
    follower_count: int
    following_count: int
    record: CommunityRecordOut
    is_following: bool = Field(description="Whether you follow this profile.")
    is_blocked: bool = Field(description="Whether you have blocked this profile.")
    is_me: bool


class MyProfileOut(ProfileOut):
    is_public: bool
    can_post: bool = Field(
        description="True when the profile is public and was not hidden by moderators."
    )
    moderation_status: ModerationStatus
    moderation_note: str | None = Field(
        default=None, description="Set when moderators hid or removed the profile."
    )


class AuthorOut(BaseModel):
    handle: str


class FollowEntryOut(BaseModel):
    handle: str
    bio: str | None = None
    since: datetime
    is_following: bool = Field(description="Whether you follow this profile.")


class FollowListOut(BaseModel):
    items: list[FollowEntryOut]


class FollowStateOut(BaseModel):
    handle: str
    is_following: bool


class BlockEntryOut(BaseModel):
    handle: str
    since: datetime


class BlockListOut(BaseModel):
    items: list[BlockEntryOut]


class BlockStateOut(BaseModel):
    handle: str
    is_blocked: bool


# ---------------------------------------------------------------------- picks
class PickCreate(BaseModel):
    """A structured, gradeable selection. There is deliberately no stake, no unit size
    and no confidence rating."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=64)
    market: PickMarket
    outcome_key: PickOutcome
    line: float | None = Field(
        default=None,
        ge=-1000,
        le=1000,
        description=(
            "Spread and total only. A spread line is the handicap of the selected side "
            "(`-3.5` for a favourite). It has to be a line a sportsbook is quoting."
        ),
    )
    analysis: str | None = Field(
        default=None, max_length=ANALYSIS_MAX, description="Optional plain text. No links."
    )


class FinalScoreOut(BaseModel):
    home: int
    away: int


class PickOut(BaseModel):
    id: str
    author: AuthorOut
    event_id: str
    event_label: str
    event_start_time: datetime
    league: str
    market: PickMarket
    outcome_key: PickOutcome
    line: float | None = None
    selection: str = Field(description="The selection in words, e.g. `Over 224.5 in A at B`.")
    price: PriceOut = Field(
        description="The best open, non-stale price when the pick was posted, set by the server."
    )
    sportsbook: SportsbookRef = Field(description="The sportsbook that offered that price.")
    posted_at: datetime
    status: PickStatus = Field(
        description=(
            "`pending` until the event is final; `graded` once graded from the final "
            "score; `void` when the data provider dropped the event before a final score."
        )
    )
    result: PickResult | None = None
    graded_at: datetime | None = None
    final_score: FinalScoreOut | None = None
    analysis: str | None = Field(
        default=None, description="Plain text exactly as posted. Escape it when rendering."
    )
    verified: Literal[True] = Field(
        default=True,
        description=(
            "Always true: every pick is structured, timestamped before the event and "
            "graded by the server. Self-reported picks do not exist."
        ),
    )
    like_count: int
    comment_count: int
    liked_by_me: bool
    is_mine: bool
    moderation_status: ModerationStatus = Field(
        description="Other than `visible` only on your own pick, after moderators hid it."
    )
    moderation_note: str | None = None
    data_mode: DataMode = Field(description="Reported by the active data provider.")


class PickPageOut(BaseModel):
    items: list[PickOut]
    next_before: str | None = Field(
        default=None, description="Pass as `before` to get the next (older) page."
    )


class LikeStateOut(BaseModel):
    pick_id: str
    liked_by_me: bool
    like_count: int


# ------------------------------------------------------------------- comments
class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_MAX, description="Plain text. No links.")


class CommentOut(BaseModel):
    id: str
    pick_id: str
    author: AuthorOut
    body: str | None = Field(
        default=None,
        description=(
            "Plain text exactly as posted; escape it when rendering. Null on your own "
            "comment after moderators removed it."
        ),
    )
    created_at: datetime
    is_mine: bool
    moderation_status: ModerationStatus
    moderation_note: str | None = None


class CommentPageOut(BaseModel):
    items: list[CommentOut]
    next_before: str | None = Field(
        default=None, description="Pass as `before` to get the next (older) page."
    )


# -------------------------------------------------------------------- reports
class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: ReportTargetType
    target_id: str = Field(
        min_length=1,
        max_length=32,
        description="The pick id, the comment id or, for a profile, its handle.",
    )
    reason: ReportReason
    details: str | None = Field(default=None, max_length=REPORT_DETAILS_MAX)


class ReportOut(BaseModel):
    """Your own report, or the review entry opened when you edited a profile that
    moderators hid or removed. What moderators decided is not shown here."""

    id: str
    target_type: ReportTargetType
    target_id: str
    reason: ReportReason
    details: str | None = None
    status: ReportStatus
    created_at: datetime


# ---------------------------------------------------------------- leaderboard
class LeaderboardRowOut(BaseModel):
    rank: int
    handle: str
    record: CommunityRecordOut


class LeaderboardOut(BaseModel):
    window: LeaderboardWindow
    league: str | None = None
    minimum_graded_picks: int
    ranked_by: Literal["wilson_lower_bound"] = "wilson_lower_bound"
    items: list[LeaderboardRowOut]
    method: str
    caveat: str = Field(description="Past results do not predict future results.")
    as_of: datetime
    data_mode: DataMode


# --------------------------------------------------------------------- export
class CommunityExportOut(BaseModel):
    """The community part of the account export."""

    profile: MyProfileOut | None = None
    picks: list[PickOut] = Field(default_factory=list)
    comments: list[CommentOut] = Field(default_factory=list)
    following: list[str] = Field(default_factory=list, description="Handles you follow.")
    likes: list[str] = Field(default_factory=list, description="Ids of picks you liked.")
    blocks: list[str] = Field(default_factory=list, description="Handles you blocked.")
    reports: list[ReportOut] = Field(
        default_factory=list,
        description=(
            "Reports you made, and the review entries opened when you edited a profile "
            "that moderators hid or removed (`target_type` `profile`, your own handle)."
        ),
    )


# ----------------------------------------------------------------- moderation
class AdminReportPartyOut(BaseModel):
    user_id: str
    handle: str | None = None
    status: str = Field(description="Account status: active or suspended.")


class AdminReportOut(BaseModel):
    id: str
    status: ReportStatus
    created_at: datetime
    reason: ReportReason
    details: str | None = None
    target_type: ReportTargetType
    target_id: str
    target_exists: bool = Field(description="False when the content was deleted since.")
    target_text: str | None = Field(
        default=None, description="The reported analysis, comment or bio, as stored."
    )
    target_summary: str | None = Field(
        default=None, description="For a pick: the selection and the event."
    )
    target_moderation_status: ModerationStatus | None = None
    reported_text: str | None = Field(
        default=None,
        description=(
            "The analysis, comment or bio as it was when the report was made, kept on the "
            "report. Null for reports made before this copy was kept, and when there was "
            "no text."
        ),
    )
    reported_summary: str | None = Field(
        default=None,
        description=(
            "Like `target_summary`, as it was when the report was made: for a pick the "
            "selection and the event, for a profile `@handle`."
        ),
    )
    target_changed_since_report: bool = Field(
        default=False,
        description=(
            "True when the content was deleted since the report was made, or its text or "
            "summary differs from `reported_text` and `reported_summary`. Always false for "
            "a report made before the copy was kept, unless the content was deleted."
        ),
    )
    author_edit: bool = Field(
        default=False,
        description=(
            "True for an entry the API opened itself because the author edited a profile "
            "that moderators hid or removed. The edited profile stays hidden or removed "
            "until an administrator restores it. `reporter` is then the author."
        ),
    )
    author_earlier_removals: int = Field(
        default=0,
        description=(
            "How many times moderators hid or removed content of this author: one per "
            "decision, however many reports it closed, including content that was deleted "
            "or restored since. For an open report every such decision so far; for a "
            "resolved report the decisions up to its own, not counting the one that closed "
            "it. Counted from the reports that are kept, so a decision whose every report "
            "was deleted with an account is no longer counted."
        ),
    )
    author: AdminReportPartyOut
    reporter: AdminReportPartyOut
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_action: ReportResolution | None = None
    resolution_note: str | None = None


class AdminReportListOut(BaseModel):
    items: list[AdminReportOut]
    total: int = Field(description="Reports with that status, before `limit` and `offset`.")
    limit: int
    offset: int


class ResolveReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ResolveAction
    note: str = Field(
        min_length=3,
        max_length=500,
        description="Why. Stored on the report and in the audit log.",
    )


class RestoreContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: ReportTargetType
    target_id: str = Field(
        min_length=1,
        max_length=32,
        description="The pick id, the comment id or, for a profile, its current handle.",
    )
    note: str = Field(
        min_length=3,
        max_length=500,
        description="Why. Stored on any report it closes and in the audit log.",
    )


class RestoredContentOut(BaseModel):
    target_type: ReportTargetType
    target_id: str
    moderation_status: ModerationStatus = Field(description="Always `visible` after a restore.")
    reports_closed: int = Field(
        description="Open reports on the content that were closed as `restore_content`."
    )


class AdminCommunityOverviewOut(BaseModel):
    profiles: int
    public_profiles: int
    picks: int
    graded_picks: int
    comments: int
    open_reports: int
    hidden_or_removed_items: int
