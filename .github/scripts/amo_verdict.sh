#!/usr/bin/env bash
# What did the AMO submission actually do?
#
# `web-ext sign --channel listed` uploads the version and then polls for a
# signed file. A listed submission sits in review, so that poll can end without
# a file — the one non-zero exit worth tolerating. It has to be told apart from
# a rejection, which must fail loudly.
#
# This is a script rather than a grep inside the workflow because the first
# version of that grep accepted any log mentioning "validation" — a word that
# appears in "Waiting for validation…" whether AMO accepts the upload or refuses
# it with a 400. It reported a rejected submission as success. The tests feed it
# that exact log.
#
# usage: amo_verdict.sh <log-file> <web-ext-exit-status>
set -u
log=${1:?usage: amo_verdict.sh <log-file> <web-ext-exit-status>}
status=${2:?usage: amo_verdict.sh <log-file> <web-ext-exit-status>}

if [ "$status" -eq 0 ]; then
    echo "submitted: web-ext finished with a signed file"
    exit 0
fi

# A refusal is a refusal, whatever else the log says.
#
# The duplicate case comes first: re-submitting a version AMO already has comes
# back as a 400 ("Version 0.5.2 already exists"), which is not a failure — it
# means an earlier run already did the work, and every release tag submits the
# extension version whether or not the extension changed.
if grep -qiE "already exists|already been uploaded|version .* already" "$log"; then
    echo "::notice title=Already on AMO::This version is already in the listing — nothing to submit."
    echo "submitted: this version is already on AMO"
    exit 0
fi

if grep -qiE "submission failed|bad request|unauthorized|forbidden|client error|not acceptable" "$log"; then
    echo "::error title=AMO refused the submission::The WebExtError above is the message to fix."
    echo "refused: AMO rejected the submission"
    exit 1
fi

# Mozilla's wording for "the upload is in, the signature is not coming yet".
if grep -qiE "took too long|timed out|timeout|still waiting" "$log"; then
    echo "::notice title=Submitted to AMO::The upload reached Mozilla; the CLI stopped waiting for a signature, which is normal while a listing is in review."
    echo "submitted: the upload reached AMO and the version is in review"
    exit 0
fi

# Fail safe: a wording we have not seen before must never be read as success.
echo "::error title=AMO submission unclear::web-ext exited $status without a recognisable verdict — read the log above."
echo "failed: no recognisable AMO verdict"
exit 1
