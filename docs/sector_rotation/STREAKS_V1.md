# Average consecutive green/red day streak

Thread: Tool: Sector Rotation Tracker

Sector Detail adds separate green and red average streak lengths, formatted to
two decimals, with completed-run counts. Both main sectors and Tech & AI use the
same component. It appears for return measures, alongside directional averages.

The sample is the 60 reference sessions strictly before the selected day, from
full history rather than the filtered display. Each fully observed completed
run contributes equally to its sign's arithmetic average run length.
Positive daily price return is green in Daily Return mode; positive excess
return versus SPY is green in Relative mode. Negative values are red. Flat
values (absolute value <= 1e-10) break runs and do not count as either color.

Only runs whose start and finish are observed inside the sample are counted.
Boundary-touching runs and runs adjacent to missing/nonfinite observations are
excluded. The selected day cannot finish a sample run or enter its average.
No eligible runs produce a dash, never a fabricated zero. Partial loaded history
is explicitly labeled; sample dates, sessions and missing counts are visible.
Rank modes do not reinterpret all-positive rank numbers as green price days.

Validation includes four streak calculation checks for run weighting, boundaries,
flat/missing observations, relative-vs-price direction and future exclusion,
plus render verification of two-decimal values and measure labels. The full
suite before the final render addition passed 30 checks; the added render check
also passes. Production build is required before deployment. Authenticated
browser interaction remains unverified.

The panel also reports the longest eligible completed green streak and red
streak in whole days, using exactly the same sample and eligibility rules.
No eligible streaks display a dash for both the mean and maximum.
