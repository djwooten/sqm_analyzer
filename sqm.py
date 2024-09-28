from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


class SQM:
    """Container for SQM settings and measurements"""

    # # UTC Date & Time, Local Date & Time, Temperature, Voltage, MSAS, Record type
    DATETIME_UTC = 0
    DATETIME_LOCAL = 1
    TEMPERATURE = 2
    VOLTAGE = 3
    MSAS = 4
    RECORD_TYPE = 5

    def __init__(self, uploaded_file):
        self.header = SQM._read_header(uploaded_file)

        try:
            self.latitude, self.longitude, self.elevation = (
                float(i)
                for i in self.header["Position (lat, lon, elev(m))"].split(", ")
            )
        except (ValueError, KeyError):
            self.latitude, self.longitude, self.elevation = None, None, 0

        self.timezone = ZoneInfo(self.header["Local timezone"])

        self.data = pd.read_csv(
            uploaded_file,
            skiprows=int(self.header["Number of header lines"]),
            sep=";",
            header=None,
        )
        self.data["datetime"] = [
            datetime.fromisoformat(t + "Z") for t in self.data[self.DATETIME_UTC]
        ]
        self.data["local_datetime"] = [
            datetime.fromisoformat(t) for t in self.data[self.DATETIME_LOCAL]
        ]
        self.data["local_datetime"] = [
            datetime(
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
                tzinfo=self.timezone,
            )
            for dt in self.data["local_datetime"]
        ]
        # Formula: NELM=7.93-5*log(10^(4.316-(Bmpsas/5))+1)
        # Source: Olof Carlin, Nils. About Bradley E. Schaefer: Telescopic limiting Magnitudes . . . .
        # Web page discussion of brightness in Schaefer (1990) and Clark (1994).
        # http://w1.411.telia.com/~u41105032/visual/Schaefer.htm (accessed 7/2003)
        # via http://unihedron.com/projects/darksky/NELM2BCalc.html
        self.data["NELM"] = 7.93 - 5 * np.log(
            10.0 ** (4.316 - (self.data[SQM.MSAS] / 5.0)) + 1.0
        )

    @staticmethod
    def merge_sqm_objects(objects):
        return objects

    @staticmethod
    def _read_header(uploaded_file) -> dict:
        header = {}

        if isinstance(uploaded_file, str):
            infile = open(uploaded_file)
        else:
            stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
            string_data = stringio.read()
            infile = string_data.split("\n")

        for line in infile:
            if line.startswith("#"):
                line = line.strip("#").strip()
                fields = line.split(": ")
                if len(fields) == 2:
                    header[fields[0]] = fields[1]
                elif "END OF HEADER" in line:
                    break

        if isinstance(uploaded_file, str):
            infile.close()
        return header

    @staticmethod
    def is_same_device(device, other):
        """
        # Moving / Stationary position: STATIONARY
        # Moving / Fixed look direction: FIXED
        # SQM serial number: 6595
        """
        return (
            device.latitude == other.latitude
            and device.longitude == other.longitude
            and device.header["SQM serial number"] == other.header["SQM serial number"]
            and device.header["Moving / Stationary position"]
            == other.header["Moving / Stationary position"]
            and device.header["Moving / Fixed look direction"]
            == other.header["Moving / Fixed look direction"]
        )
