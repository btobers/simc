import sys

import geopandas as gpd
import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
import sys
from pyproj import Transformer

# These functions must return a pandas dataframe with the
# following cols -
# ["x", "y", "z", "datum"]
# Where XYZ are planetocentric radar platform location
# and datum should be all zeros if no time shift is required, otherwise the
# time shift in seconds

# areoidPath = "/home/mchristo/proj/simc/dem/mega_128ppd.tif"
areoidPath = "../dem/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif"

def get_xformer(crs_from, crs_to):
    return Transformer.from_crs(crs_from=crs_from, crs_to=crs_to)

def GetNav_MARSIS(navfile, navsys, xyzsys):
    c = 299792458
    rec_t = np.dtype(
        [
            ("SCET_FRAME_WHOLE", ">u4"),
            ("SCET_FRAME_FRAC", ">u2"),
            ("GEOMETRY_EPHEMERIS_TIME", ">f8"),
            ("GEOMETRY_EPOCH", "V23"),
            ("MARS_SOLAR_LONGITUDE", ">f8"),
            ("MARS_SUN_DISTANCE", ">f8"),
            ("ORBIT_NUMBER", ">u4"),
            ("TARGET_NAME", "V6"),
            ("TARGET_SC_POSITION_VECTOR", ">f8", 3),
            ("SPACECRAFT_ALTITUDE", ">f8"),
            ("SUB_SC_LONGITUDE", ">f8"),
            ("SUB_SC_LATITUDE", ">f8"),
            ("TARGET_SC_VELOCITY_VECTOR", ">f8", 3),
            ("TARGET_SC_RADIAL_VELOCITY", ">f8"),
            ("TARGET_SC_TANG_VELOCITY", ">f8"),
            ("LOCAL_TRUE_SOLAR_TIME", ">f8"),
            ("SOLAR_ZENITH_ANGLE", ">f8"),
            ("DIPOLE_UNIT_VECTOR", ">f8", 3),
            ("MONOPOLE_UNIT_VECTOR", ">f8", 3),
        ]
    )

    auxData = np.fromfile(navfile, dtype=rec_t)

    df = pd.DataFrame(
        auxData["TARGET_SC_POSITION_VECTOR"] * 1e3, columns=["x", "y", "z"]
    )

    cmt = """
    # Find datum time with areoid
    try:
        aer = rio.open(areoidPath, "r")
    except Exception as e:
        print(e)
        print("Unable to open areoid file, is it at : " + areoidPath + " ?")
        sys.exit(1)

    aerX, aerY, aerZ = pyproj.transform(
        xyzsys, aer.crs, df["x"].to_numpy(), df["y"].to_numpy(), df["z"].to_numpy()
    )

    iy, ix = aer.index(aerX, aerY)
    ix = np.array(ix)
    iy = np.array(iy)

    # Temp fix mola meters/pix issue
    ix[ix > aer.width - 1] = aer.width - 1
    ix[ix < 0] = 0

    zval = aer.read(1)[iy, ix]"""

    df["r"] = np.sqrt(df["x"] ** 2 + df["y"] ** 2 + df["z"] ** 2)

    angle = np.abs(np.arctan(df["z"] / np.sqrt(df["x"] ** 2 + df["y"] ** 2)))

    a = 3396190
    b = 3376200

    marsR = (a * b) / np.sqrt(
        (a ** 2) * (np.sin(angle) ** 2) + (b ** 2) * (np.cos(angle) ** 2)
    )

    df["datum"] = (df["r"] - marsR) * 2.0 / c - (256 * 1.0 / 1.4e6)

    # df["datum"] = ((df["r"] - zval+3396000) * 2.0 / c) - (
    #    256 * 1/2.8e6
    # )

    return df[["x", "y", "z", "datum"]]


def GetNav_akHypo(navfile, navsys, xyzsys):
    df = pd.read_csv(navfile)
    df["datum"] = np.zeros(len(df))
    return df[["x", "y", "z", "datum"]]


def GetNav_DJI(navfile, navsys, xyzsys):
    xformer = get_xformer(navsys, xyzsys)

    df = pd.read_csv(navfile, sep=",")

    print(df)
    c = 299792458
    df["x"], df["y"], df["z"] = xformer.transform(
        df["lon"].to_numpy(),
        df["lat"].to_numpy(),
        df["hgt"].to_numpy(),
    )
    df["datum"] = 0 * df["x"]
    traceSamples = 1000
    # df["datum"] = (10 * 2.0 / c - (10e-9* (traceSamples / 2)))
    return df[["x", "y", "z", "datum"]]


def GetNav_akHDF(navfile, navsys, xyzsys):
    xformer = get_xformer(navsys, xyzsys)
    h5 = h5py.File(navfile, "r")
    if "nav0" in h5["ext"].keys():
        nav = h5["ext"]["nav0"][:]
        df = pd.DataFrame(nav)

    elif "loc0" in h5["raw"].keys():
        nav = h5["raw"]["loc0"][:]
        df = pd.DataFrame(nav)
        # Interpolate non-unique values
        hsh = nav["lat"] + nav["lon"] * 1e4
        idx = np.arange(0, len(hsh), 1)
        uniq, uidx = np.unique(hsh, return_index=True)
        uidx = np.sort(uidx)
        uidx[-1] = len(hsh) - 1  # Handle end of array
        df["lat"] = np.interp(idx, uidx, df["lat"][uidx])
        df["lon"] = np.interp(idx, uidx, df["lon"][uidx])
        df["hgt"] = np.interp(idx, uidx, df["hgt"][uidx])

    else:
        h5.close()
        print("No valid navigation data found in file %s" % navfile)
        sys.exit()

    h5.close()
    df["x"], df["y"], df["z"] = xformer.transform(
        df["lon"].to_numpy(),
        df["lat"].to_numpy(),
        df["hgt"].to_numpy(),
    )

    df["datum"] = 0 * df["x"]

    return df[["x", "y", "z", "datum"]]


def GetNav_bsiHDF(navfile, navsys, xyzsys):
    xformer = get_xformer(navsys, xyzsys)
    h5 = h5py.File(navfile, "r")
    if 'restack' in h5.keys():
        grp = 'restack'
    else:
        grp = 'raw'
    df = pd.DataFrame(h5[grp]["gps0"][:])
    h5.close()
    df["x"], df["y"], df["z"] = xformer.transform(
        df["lon"].to_numpy(),
        df["lat"].to_numpy(),
        df["hgt"].to_numpy(),
    )
    df["datum"] = 0 * df["x"]

    return df[["x", "y", "z", "datum"]]


def GetNav_FPBgeom(navfile, navsys, xyzsys):
    c = 299792458
    geomCols = [
        "trace",
        "time",
        "lat",
        "lon",
        "marsRad",
        "elev",
        "radiVel",
        "tangVel",
        "SZA",
        "phaseD",
    ]

    dtypes = {
        "lat": np.float128,
        "lon": np.float128,
        "elev": np.float128,
    }
    df = pd.read_csv(navfile, names=geomCols, dtype=dtypes)

    # Planetocentric lat/lon/radius to X/Y/Z - no need for navsys in this one
    df["x"] = (
        (df["elev"] * 1000)
        * np.cos(np.radians(df["lat"]))
        * np.cos(np.radians(df["lon"]))
    )
    df["y"] = (
        (df["elev"] * 1000)
        * np.cos(np.radians(df["lat"]))
        * np.sin(np.radians(df["lon"]))
    )
    df["z"] = (df["elev"] * 1000) * np.sin(np.radians(df["lat"]))

    df["datum"] = (1e3 * (df["elev"] - df["marsRad"]) * 2.0 / c) - (1800.0 * 37.5e-9)

    return df[["x", "y", "z", "datum"]]


def GetNav_QDAetm(navfile, navsys, xyzsys):
    xformer = get_xformer(navsys, xyzsys)

    c = 299792458
    etmCols = [
        "trace",
        "epoch",
        "alt",
        "sza",
        "lat",
        "lon",
        "molaNadir",
        "vrad",
        "vtan",
        "dist",
        "tshift",
        "radius",
        "utc0",
        "utc1",
    ]

    df = pd.read_csv(navfile, names=etmCols, sep="\s+")

    df["x"], df["y"], df["z"] = xformer.transform(
        df["lon"].to_numpy(),
        df["lat"].to_numpy(),
        (1000 * df["alt"]).to_numpy(),
    )
    # df["datum"] = df["tshift"] * 1e-6

    df["datum"] = (2 * df["alt"] / c) - (1800 * 37.5e-9)

    # plt.plot(np.gradient(df["tshift"]))
    # plt.plot((df["tshift"]/37.5e-9),'.')
    # plt.show()
    # sys.exit()

    rad = np.sqrt(df["x"] ** 2 + df["y"] ** 2 + df["z"] ** 2)

    # plt.plot(rad)
    # plt.show()
    # sys.exit()

    return df[["x", "y", "z", "datum"]]


def GetNav_LRS(navfile, navsys, xyzsys):
    fs = 6.25e6

    df = pd.read_csv(navfile, sep=",")

    # df["datum"] = df["delay"]/1e6
    ### Roberto ###
    c = 299792458
    spacecraftHeight = 30000  # m
    samplingFrequency = 37.5e-9
    traceSamples = 4800

    df["datum"] = spacecraftHeight * 2.0 / c - (samplingFrequency * (traceSamples / 2))
    ### Roberto ###

    return df[["x", "y", "z", "datum"]]


def GetNav_simpleTest(navfile, navsys, xyzsys):
    navCols = ["x", "y", "z"]
    df = pd.read_csv(navfile, names=navCols)

    # No redatum
    df["datum"] = np.zeros(df.shape[0])

    return df[["x", "y", "z", "datum"]]
