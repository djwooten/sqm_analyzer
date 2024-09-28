from datetime import datetime, timedelta

from astral import LocationInfo, moon, sun


class Filter:
    def __init__(self, column, value):
        self.column = column
        self.value = value
        self.comparitor = ""

    def evalulate(self, value):
        return True


class FilterLessThan(Filter):
    def __init__(self, column, value):
        super().__init__(column, value)
        self.comparitor = "<"

    def evaluate(self, df):
        return df[self.column] < self.value


def _get_astral_observer(latitude, longitude, elevation, timezone):
    location_info = LocationInfo(
        "_name",
        "_region",
        timezone,
        latitude,
        longitude,
    )
    observer = location_info.observer
    observer.elevation = elevation
    return observer


def compute_astral_values(data, latitude, longitude, elevation, timezone):
    """Calculate moon and sun values

    Adds the following columns to `data`:
     - "moon_phase" from 0 (new moon) to 1 (full moon)
     - "moon_elevation" above the horizon in degrees
     - "sun_elevation" above the horizon in degrees

    :param pd.DataFrame data: SQM data, which must have a "datetime" column defined
    :param astral.Observer observer: Observer object with latitude, longitude, and elevation
    """
    observer = _get_astral_observer(latitude, longitude, elevation, timezone)

    # Get moon phase from 0 (new moon) to 1 (full moon)
    data["moon_phase"] = [moon.phase(dt) for dt in data["datetime"]]
    mp = data["moon_phase"]
    data["moon_phase"] = (
        1 - abs(mp - 14) / 14.0
    )  # 14 is a full moon, < 14 is waxing, > 14 is waning

    # Get moon and sun elevations
    data["moon_elevation"] = [
        moon.elevation(observer, at=dt)
        #            max(moon.elevation(_observer, at=dt), 0)
        for dt in data["datetime"]
    ]
    data["sun_elevation"] = [
        sun.elevation(observer, dateandtime=dt) for dt in data["datetime"]
    ]


def label_days_and_nights(df, elevation, night_filters=[]):
    """Label consecutive periods of dark as nights, and light as days

    This adds the following columns to `df`
      - "is_night" - bool if it is night according to the night_filters
      - "group" - a string like "day_1" or "night_2" uniquely identifying consecutive timepoints with same night value

    Note that it is possible to get something like "night_3, day_4, night_5" all within a single night, for instance
    during a full moon. There may be a brief period after the sun goes down before the moon comes up at dusk, and
    vice versa at dawn, where the classification shifts (depending on filter values)

      dddd    dddd    dddd    ddd
    nn    nnnn    nnnn    nnnn   nnn
    |=======|=======|=======|======|

    """
    previous_dt = datetime.fromisoformat("1990-01-01T00:00:00.000Z")
    previous_group = "night"
    group_idx = -1
    group_labels = []

    df["is_night"] = True
    for filter in night_filters:
        df["is_night"] = (df["is_night"]) & (filter.evaluate(df))
    for idx in df.index:
        dt = df.loc[idx, "datetime"]
        night = df.loc[idx, "is_night"]
        new_group = "night" if night else "day"
        if dt - previous_dt > timedelta(hours=12):
            group_idx += 1
        elif night and previous_group == "day":
            group_idx += 1
        elif not night and previous_group == "night":
            group_idx += 1
        group_labels.append(f"{new_group}_{group_idx}")
        previous_group = new_group
        previous_dt = dt
    df["group"] = group_labels
