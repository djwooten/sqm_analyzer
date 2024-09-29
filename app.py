import os

import pandas as pd
import streamlit as st

from sqm import SQM
from analysis import compute_astral_values, FilterLessThan, label_days_and_nights
from plots import make_sqm_plot

DEFAULT_MOON_ELEVATION_FILTER = 5
DEFAULT_SUN_ELEVATION_FILTER = -15


def _clear_data():
    """Clear the loaded data

    This is used when uploading a new file, and is required to clear the demo data if it was used.
    """
    # clear the device from
    if "device" in st.session_state:
        st.session_state["device"] = None

    # tell the app that we are no longer using demo data
    if "using_demo_data" in st.session_state:
        st.session_state["using_demo_data"] = False


def _load_demo_data():
    """Loads a demo dataset from the Wehle Forever Wild Tract, April 2024"""
    device = SQM("data/April24.dat")
    st.session_state["device"] = device
    st.session_state["using_demo_data"] = True


def _reset_filters():
    """Reset nighttime filters to defaults"""
    st.session_state["_slider_sun"] = DEFAULT_SUN_ELEVATION_FILTER
    st.session_state["_slider_moon"] = DEFAULT_MOON_ELEVATION_FILTER


def format_device_title(device):
    loc_name = device.header.get("Location name", "")
    loc_id = device.header.get("Instrument ID", "")
    if loc_name and not loc_id:
        return loc_name
    if loc_id and not loc_name:
        return loc_id
    return f"{loc_name} - {loc_id}"


@st.cache_data
def _prepare_df_for_download(df):
    df = df.copy()
    columns = list(df.columns)
    columns[0] = "datetime_utc"
    columns[1] = "datetime_local"
    columns[2] = "temperature"
    columns[3] = "voltage"
    columns[4] = "msas"
    columns[5] = "record_type"
    df.columns = columns
    cols = [i for i in columns if i not in ["datetime", "local_datetime"]]
    df = df[cols]
    return df.to_csv(index=None).encode("utf-8")


@st.fragment
def _add_fragment_download_button(uploaded_file):
    if uploaded_file is None or st.session_state["using_demo_data"]:
        fname = "demo.csv"
    else:
        fname = os.path.splitext(uploaded_file.name)[0] + ".csv"

    device = st.session_state["device"]
    if device is not None:
        data = _prepare_df_for_download(device.data)
        st.download_button(
            label="Download data as CSV with moon and sun values",
            data=data,
            file_name=fname,
            mime="text/csv",
        )


# Add statefulness to the app
# Remember loaded dat file to avoid reloading when sliders are adjusted
if "device" not in st.session_state:
    st.session_state["device"] = None
if "using_demo_data" not in st.session_state:
    st.session_state["using_demo_data"] = False

st.set_page_config(page_title="Sky Quality Meter Analyzer", page_icon=":milky_way:")
st.header("Sky Quality Meter Data Analyzer")

# Create the sidebar
with st.sidebar:
    # Filters
    st.header('Filters for "night" time')
    filter_sun_elevation = st.slider(
        "Sun elevation (<)",
        min_value=-30,
        max_value=0,
        value=DEFAULT_SUN_ELEVATION_FILTER,
        help="Sun elevation below the horizon in degrees. `0` is sunset.",
        key="_slider_sun",
    )
    filter_moon_elevation = st.slider(
        "Moon elevation (<)",
        min_value=-20,
        max_value=90,
        value=DEFAULT_MOON_ELEVATION_FILTER,
        help="Moon elevation above (+) or below (-) the horizon in degrees. Set to 90 to effectively ignore the moon.",
        key="_slider_moon",
    )
    st.button("Reset Filters", on_click=_reset_filters)


uploaded_file = st.file_uploader(
    "Upload an SQM .dat file",
    type=["dat"],
    on_change=_clear_data,
    help="Accepted file formats are: Unihedron SQM '.dat'",
)
st.button(
    "Load Demo Dataset",
    help="Load example dataset from Wehle Forever Wild Tract in Alabama",
    on_click=_load_demo_data,
)
if uploaded_file is not None or st.session_state["using_demo_data"]:
    if st.session_state["device"] is None:
        device = SQM(uploaded_file)
        st.session_state["device"] = device
    else:
        device = st.session_state["device"]

    night_filters = [
        FilterLessThan("sun_elevation", filter_sun_elevation),
        FilterLessThan("moon_elevation", filter_moon_elevation),
    ]

    location_info_specified = False
    if device.latitude is not None and device.longitude is not None:
        location_info_specified = True
        lat, lon, elev = device.latitude, device.longitude, device.elevation

        map_df = pd.DataFrame()
        map_df["lat"] = [lat]
        map_df["lon"] = [lon]

        compute_astral_values(device.data, lat, lon, elev, device.timezone.key)
        label_days_and_nights(device.data, elev, night_filters=night_filters)

    st.header(format_device_title(device))

    if not location_info_specified:
        st.warning(
            """
            Longitude, latitude, and elevation are missing from the file. Moon and sun metrics cannot be computed
            without these values, and are therefore missing from the plots and analyses. Please see the FAQ for
            details on how to fix this.
            """,
            icon=":material/warning:",
        )

    fig = make_sqm_plot(device.data)
    st.plotly_chart(fig, use_container_width=True)
    if location_info_specified:
        _add_fragment_download_button(uploaded_file)

    if "group" in device.data.columns:
        night_df = device.data.loc[device.data["group"].str.startswith("night")]
    else:
        night_df = device.data
    mean_msas = night_df[4].mean()
    median_msas = night_df[4].median()

    if location_info_specified:
        col1, col2, col3 = st.columns(3)
        col1.metric("Latitude", f"{lat} °N" if lat > 0 else f"{-lat} °S")
        col2.metric("Longitude", f"{lon} °E" if lon > 0 else f"{-lon} °W")
        col3.metric("Elevation", f"{elev}m")
        st.map(map_df)

    st.header("Nighttime Metrics")
    filter_df = pd.DataFrame(
        columns=[filter.column for filter in night_filters],
        index=["comparison", "value"],
    )
    for filter in night_filters:
        filter_df[filter.column] = [filter.comparitor, filter.value]
    filter_df = filter_df.transpose()

    col1, col2 = st.columns(2)
    col1.metric("MSAS (mean)", f"{mean_msas:0.2f}")
    col2.metric("MSAS (median)", f"{median_msas:0.2f}")
    if location_info_specified:
        st.subheader(
            "Night Filters",
            help="These filters are applied to isolate only the data that corresponds to the moonless parts of nights. See sidebar on left to adjust filter values.",
        )
        st.table(filter_df)

    st.subheader("Device Metadata", help="Metadata from the file header")
    st.json(device.header)


with st.sidebar:
    # How to use
    st.header("FAQ")
    with st.expander("What file formats are accepted?"):
        st.write("Unihedron `.dat` files produced by the Unihedron Device Manager")

    with st.expander("How do I interpret the plots?"):
        st.write(
            "There are three plots stacked vertically on top of one another. Below them is a range selector that can be used to show specific date ranges."
        )
        st.subheader("Moon Elevation")
        st.write("""
            The top plot shows the moon elevation above the horizon, in degrees. The horizontal line here indicates the
            location of the horizon. When the moon is above that line, then the moon is above the horizon.
        """)
        st.subheader("Moon Phase")
        st.write("""
            The middle plot shows the moon phase from 0 (new moon) to 1 (full moon) and back.
        """)

        st.subheader("MSAS")
        st.write("""
            The bottom plot shows the MSAS in units of mag/arcsec^2. When this value is high, it indicates a dark sky.
            When the value is low (0) it indicates a bright sky.
        """)

        st.subheader("Background shading")
        st.write("""
            The background color indicates whether the timepoint is considered daylight or nighttime, based on the
            filters. Yellow/gold indicates daytime, and dark blue indicates nighttime.
        """)

    with st.expander("How can I save a copy of the plot?"):
        st.write("""
            If you hover over the plot area, a control panel will appear on the top right which contains an option to
            download the image.
        """)

    with st.expander(
        "My longitude, latitude, and elevation are missing. How can I fix this?"
    ):
        st.markdown("""
            The Unihedron `.dat` file format is a plain text file that can be edited in text editors, such as Notepad
            in Windows. At the top of the file there is a "header" section consisting of lines starting with `"#"` like
            ```
            # Light Pollution Monitoring Data Format 1.0
            # URL: http://www.darksky.org/measurements
            # Number of header lines: 42
            ...
            # END OF HEADER
            ```
            Make sure the header includes a line like
            ```
            # Position (lat, lon, elev(m)): 32.04499, -85.469629, 120
            ```
            where you insert your own lat, lon, and elevation values. (Note: this MUST come before the `# END OF
            HEADER`
            line!)

            Afterwords, make sure the `# Number of header lines:` value is still correct. If you added an entirely new
            line then you should increase the number by 1. If you just filled your lat, lon, and elevation values into
            an existing line, then you will not need to modify the `# Number of header lines:` value.
        """)

    with st.expander(
        "The nighttime periods are not lining up with the dark MSAS readings. How can I fix this?"
    ):
        st.write("""
            This may be because your latitude, longitude, and elevation values are wrong. See the FAQ answer about
            fixing latitude, longitude, and elevation to check those values.
        """)

        st.write("""
            If the latitude, longitude, and elevation values are correct then the time may be out of sync. This app
            performs all celestial body calculations using UTC time, which is the first column in the `.dat` file.
            Unfortunatley there is no easy solution to resolving out-of-sync data, but you can try to adjust these
            values in the raw `.dat` file to correct the time.
        """)

        st.write("""
            If you have checked the above and are confident that there is no problem with the data, then this may be
            a bug in the software. You can review the source code at https://github.com/djwooten/sqm_analyzer to
            troubleshoot the issue.
        """)

    with st.expander("How can I use this to configure my SQM device?"):
        st.write("""
            This software does not interact directly with SQM devices. Consider alternatives like Unihedron Device
            Manager or Knightware SQM Reader.
        """)

    with st.expander("How do I report a bug?"):
        st.write("""
            This software is not actively maintained. However the source code is open and available at https://github.com/djwooten/sqm_analyzer/
        """)

    with st.container(height=None, border=True):
        st.header("Credits")
        st.write("""
            This software was written by David Wooten. The source code is available at https://github.com/djwooten/sqm_analyzer. It is available under the BSD-3-Clause license.
        """)
        st.write(
            "Moon and sun values are calculated using the [astral](https://pypi.org/project/astral) python library."
        )
        st.write(
            "This app is written in [streamlit](https://streamlit.io) and hosted on their (Community Cloud)[https://streamlit.io/cloud]"
        )
        st.write("""
            NELM is estimated using the formula at http://unihedron.com/projects/darksky/NELM2BCalc.html.
        """)
