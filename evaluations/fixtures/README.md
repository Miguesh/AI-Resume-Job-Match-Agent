# Synthetic evaluation fixtures

`synthetic-v1.json` was written specifically for this open-source repository. It contains
no copied resume, job advertisement, personal record, or production data. All people,
companies, accomplishments, phone numbers, and email addresses are fictional. Email
addresses use the IANA-reserved `example.com` domain and telephone numbers use the fictional
North American `555-01xx` range.

To the extent possible under law, the fixture content is dedicated under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The benchmark code remains
covered by the repository's MIT license.

The fixtures are intended only for deterministic regression testing. Their small size,
English-only language, plain-text format, and intentionally explicit wording mean that
their metrics cannot be generalized to real resumes, applicant populations, ATS products,
or hiring outcomes. Do not replace them with private resumes. New cases must be synthetic
or carry explicit redistribution permission and a documented provenance review.

Every dataset change requires a version increment. Existing expected scores are golden
outputs for the named score policy and should change only when a reviewed policy or
extraction change intentionally changes behavior.
