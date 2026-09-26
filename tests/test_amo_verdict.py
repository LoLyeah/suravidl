"""The AMO submission verdict, tested against the log that taught it.

The first version of this check lived in the workflow as
`grep -qiE "uploaded|awaiting review|validation|submitted"` and it reported a
refused submission as success: "Waiting for validation…" appears in that log
whether AMO accepts the upload or answers 400. The refusal below is the real one
from that run, kept verbatim as a fixture so the check cannot drift back.
"""
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / ".github/scripts/amo_verdict.sh"

REAL_REFUSAL = """Building web extension from /tmp/ffext
Waiting for validation...

WebExtError: Submission failed (2): Bad Request
{
  "homepage": [
    "You must provide an object of {lang-code:value}."
  ],
  "support_url": [
    "You must provide an object of {lang-code:value}."
  ]
}
    at file:///home/runner/.npm/_npx/b04a1c8f1afa246c/node_modules/web-ext/lib/cmd/sign.js:101:13
"""


def _verdict(log: str, status: int):
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
        fh.write(log)
        path = fh.name
    p = subprocess.run(["bash", str(SCRIPT), path, str(status)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def test_the_refusal_that_fooled_it_is_still_a_refusal():
    """This exact log reported itself as success once — 'Waiting for
    validation…' is printed before AMO's 400."""
    code, out = _verdict(REAL_REFUSAL, 1)
    assert code == 1, out
    assert "refused" in out


def test_a_signed_submission_passes():
    code, out = _verdict("Signed and downloaded suravidl-0.5.2-an+fx.xpi\n", 0)
    assert code == 0, out
    assert "submitted" in out


def test_a_listing_left_in_review_counts_as_submitted():
    """A listed version goes into review, so the CLI's wait ends without a
    file — the upload is what matters."""
    code, out = _verdict("Waiting for validation...\nSigning took too long\n", 1)
    assert code == 0, out
    assert "review" in out


def test_an_unfamiliar_failure_stays_a_failure():
    """Fail safe: wording from Mozilla we have not seen must not be read as
    success — the run fails and the log is right there."""
    code, out = _verdict("something new went wrong\n", 1)
    assert code == 1, out
    assert "no recognisable AMO verdict" in out


def test_a_401_is_never_read_as_a_timeout():
    code, out = _verdict("WebExtError: 401 Unauthorized\n", 1)
    assert code == 1
    assert "refused" in out


def test_the_workflow_uses_the_script_and_not_its_own_grep():
    wf = (ROOT / ".github/workflows/amo.yml").read_text()
    assert "bash .github/scripts/amo_verdict.sh" in wf
    assert 'grep -qiE "uploaded|awaiting review|validation|submitted"' not in wf, \
        "the verdict belongs in the tested script"
