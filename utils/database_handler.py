from functools import lru_cache
import os.path as path
import pandas as pd
import sqlite3


class DataframeConnection:
    """
    A class to connect to a database file and retrieve table names and dataframes

    :param db_file: The path to the database file
    """
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.file_type = path.splitext(db_file)[1].lower()

    def get_table_or_sheet_names(self) -> list:
        """
        Gets the names of all tables or sheets in the database file

        :return: A list of table or sheet names
        """
        if self.file_type in (".db", ".db3", ".sqlite", ".sqlite3"):
            return self._get_sqlite_table_names()
        elif self.file_type == ".xlsx":
            return self._get_excel_sheet_names()
        elif self.file_type == ".csv":
            return ["CSV file"]
        else:
            raise ValueError(f"Unsupported file type: {self.file_type}")
    
    @lru_cache(maxsize=1)
    def get_df(self, table_name: str) -> pd.DataFrame:
        """
        Gets a dataframe of the data in the specified table or sheet

        :param table_name: The name of the table or sheet to get the data from
        :return: A dataframe of the data in the specified table or sheet
        """
        if self.file_type in (".db", ".db3", ".sqlite", ".sqlite3"):
            return self._get_sqlite_dataframe(table_name)
        elif self.file_type == ".xlsx":
            return self._get_excel_dataframe(table_name)
        elif self.file_type == ".csv":
            return self._get_csv_dataframe()
        else:
            raise ValueError(f"Unsupported file type: {self.file_type}")
    
    @lru_cache(maxsize=1)
    def get_filtered_sorted_df(self, table_name: str, sort_column: str | None = None, sort_order: bool = False, search_query: str | None = None) -> pd.DataFrame:
        """
        Gets a filtered and sorted dataframe of the data in the specified table or sheet

        :param table_name: The name of the table or sheet to get the data from
        :param sort_column: The name of the column to sort by
        :param sort_order: The order to sort by, True for ascending, False for descending
        :param search_query: The string to search for in the dataframe
        :return: A filtered and sorted dataframe
        """
        df = self.get_df(table_name=table_name)
        if search_query:
            df = df[df.astype(str).apply(lambda row: row.str.contains(search_query, case=False, regex=False)).any(axis=1)]
        if sort_column:
            df = df.sort_values(by=sort_column, ascending=sort_order)
        return df

    def _get_sqlite_table_names(self) -> list:
        with sqlite3.connect(self.db_file) as conn:
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)["name"].tolist()
        return [name for name in tables if not name.startswith("sqlite_autoindex_")]

    def _get_excel_sheet_names(self) -> list:
        return list(pd.read_excel(self.db_file, sheet_name=None).keys())

    def _get_sqlite_dataframe(self, table_name: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df

    def _get_excel_dataframe(self, table_name: str) -> pd.DataFrame:
        return pd.read_excel(self.db_file, sheet_name=table_name, parse_dates=True, date_parser=pd.to_datetime)

    def _get_csv_dataframe(self) -> pd.DataFrame:
        # TODO: Fix CSV datetime parsing
        try:
            return pd.read_csv(self.db_file, on_bad_lines="error", encoding="utf-8", engine="python")
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except (TypeError, ValueError):
            return pd.read_csv(self.db_file, sep=";", on_bad_lines="warn", encoding="utf-8", engine="python")
