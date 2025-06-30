# (c) 2018-2023 Tim Molteno (tim@elec.ac.nz)

import datetime
import urllib.request
import os
import traceback
import logging
import json

import sky_object
import tart.util.utc as utc


class FileCache(sky_object.SkyObject):
    def __init__(self, name):
        sky_object.SkyObject.__init__(self, name)
        self.cache_root = "./orbit_data/{}".format(self.name)
        self.last_download_attempt = {}
        self.cache = {}
        self.ban_file = "./orbit_data/celestrak_ban.json"

    def get_url(self, utc_date):
        doy = "%.3d" % utc_date.yday()
        yy = "%.2d" % (utc_date.year()-2000)
        yyyy = utc_date.year()
        path = f"daily/{yyyy}/brdc/brdc{doy}0.{yy}n"
        return f"ftp://cddis.gsfc.nasa.gov/gps/data/{path}"

    def get_local_filename(self, utc_date):
        return "{}/{}/{}.dat".format(utc_date.year, utc_date.month, utc_date.day)

    def get_local_path(self, fname):
        return "{}/{}".format(self.cache_root, fname)

    def create_object_from_file(self, local_path):
        # Override to create the object from the file
        pass



    def is_banned(self):
        """Check if we're currently banned from downloading"""
        try:
            if os.path.exists(self.ban_file):
                with open(self.ban_file, 'r') as f:
                    ban_data = json.load(f)
                ban_until = datetime.datetime.fromisoformat(ban_data['ban_until'])
                # Add 5-minute buffer after ban expiration
                ban_until_with_buffer = ban_until + datetime.timedelta(minutes=5)
                if datetime.datetime.now() < ban_until_with_buffer:
                    if datetime.datetime.now() < ban_until:
                        logging.info(f"Still banned until {ban_until} (+ 5 min buffer)")
                    else:
                        logging.info(f"Ban expired at {ban_until}, waiting 5 min buffer until {ban_until_with_buffer}")
                    return True
                else:
                    # Ban expired with buffer, remove file
                    os.remove(self.ban_file)
                    logging.info("Ban and buffer period expired, removing ban file")
                    return False
        except Exception as e:
            logging.warning(f"Error checking ban status: {e}")
            return False

    def set_ban(self, hours=3):
        """Set a ban period for the specified number of hours"""
        try:
            os.makedirs(os.path.dirname(self.ban_file), exist_ok=True)
            ban_until = datetime.datetime.now() + datetime.timedelta(hours=hours)
            ban_data = {
                'ban_until': ban_until.isoformat(),
                'reason': 'Celestrak rate limiting detected'
            }
            with open(self.ban_file, 'w') as f:
                json.dump(ban_data, f, indent=2)
            logging.warning(f"Ban set until {ban_until} due to rate limiting")
        except Exception as e:
            logging.error(f"Error setting ban: {e}")

    def find_latest_cached_file(self, utc_date):
        """Find the most recent cached file for this object type"""
        try:
            # Look for files in the last 7 days
            for days_back in range(7):
                check_date = utc_date - datetime.timedelta(days=days_back)
                fname = self.get_local_filename(check_date)
                local_path = self.get_local_path(fname)
                if os.path.isfile(local_path):
                    logging.info(f"Using cached file from {days_back} days ago: {local_path}")
                    return local_path, fname
        except Exception as e:
            logging.error(f"Error finding cached file: {e}")
        return None, None

    def download_file(self, url, local_file):
        try:
            os.makedirs(os.path.dirname(local_file))
        except Exception:
            pass

        # Check if we're currently banned
        if self.is_banned():
            raise RuntimeError("Currently banned from downloading. Using cached data.")

        try:
            if (url in self.last_download_attempt):
                print(f"Download Attempt: {self.last_download_attempt}")
                last_try = self.last_download_attempt[url]
                print(f"last_try: {last_try}")
                delta_seconds = (datetime.datetime.now() -
                                 last_try).total_seconds()
                if last_try and (delta_seconds < 3600):
                    raise RuntimeError(
                        f"Error ({url} -> {local_file}: Already attempted ({last_try} {delta_seconds}")

            logging.info("starting download ({} -> {}".format(url, local_file))
            self.last_download_attempt[url] = datetime.datetime.now()
            dat = urllib.request.urlopen(url)
            with open(local_file, 'wb') as w:
                w.write(dat.read())
                w.close()
            logging.info("download complete")
        except urllib.error.HTTPError as err:
            logging.exception(err)
            self.last_download_attempt[url] = datetime.datetime.now()

            # Handle 403 Forbidden specifically (rate limiting)
            if err.code == 403:
                logging.error("403 Forbidden - Setting ban for 2.5 hours")
                self.set_ban(hours=2.5)
                raise RuntimeError("Rate limited by server. Ban file created.")

            raise (err)
        except Exception as err:
            logging.exception(err)
            self.last_download_attempt[url] = datetime.datetime.now()
            raise (err)

    def get_object(self, date):
        utc_date = utc.to_utc(date)

        fname = self.get_local_filename(utc_date)
        if fname in self.cache:
            return self.cache[fname]

        try:
            local_path = self.get_local_path(fname)

            if (os.path.isfile(local_path) is False):
                self.download_file(self.get_url(utc_date), local_path)

            self.cache[fname] = self.create_object_from_file(local_path)
            return self.cache[fname]
        except Exception as error:
            # If we can't download, try to use the most recent cached file
            tb = traceback.format_exc()
            logging.error(tb)
            logging.error("Download failed. Looking for cached data...")

            # First check if the current date file exists (maybe download failed but file exists)
            local_path = self.get_local_path(fname)
            if os.path.isfile(local_path):
                try:
                    self.cache[fname] = self.create_object_from_file(local_path)
                    return self.cache[fname]
                except Exception as e:
                    logging.error(f"Failed to load existing file {local_path}: {e}")

            # Try to find the most recent cached file
            cached_path, cached_fname = self.find_latest_cached_file(utc_date)
            if cached_path and cached_fname:
                try:
                    if cached_fname not in self.cache:
                        self.cache[cached_fname] = self.create_object_from_file(cached_path)
                    # Also cache it under the requested date for future use
                    self.cache[fname] = self.cache[cached_fname]
                    return self.cache[fname]
                except Exception as e:
                    logging.error(f"Failed to load cached file {cached_path}: {e}")

            # If all else fails, raise the original error
            logging.error("No cached data available, re-raising original error")
            raise error
