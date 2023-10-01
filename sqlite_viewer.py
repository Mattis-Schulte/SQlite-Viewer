import functools
import math
import os.path as path
import pandas as pd
import sqlite3
import threading
import wx


class DatabaseConnection:
    """
    A class to connect to a database file and retrieve table names and dataframes

    :param db_file: The path to the database file
    """
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.file_type = path.splitext(db_file)[1]

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
    
    @functools.lru_cache(maxsize=1)
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
    
    @functools.lru_cache(maxsize=1)
    def get_filtered_sorted_df(self, table_name: str = None, sort_column: str = None, sort_order: bool = False, search_query: str = None) -> pd.DataFrame:
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
        with sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df

    def _get_excel_dataframe(self, table_name: str) -> pd.DataFrame:
        return pd.read_excel(self.db_file, sheet_name=table_name, parse_dates=True, date_parser=pd.to_datetime)

    def _get_csv_dataframe(self) -> pd.DataFrame:
        try:
            return pd.read_csv(self.db_file, on_bad_lines="error", encoding="utf-8", engine="python", parse_dates=True, date_parser=pd.to_datetime)
        except (TypeError, ValueError):
            return pd.read_csv(self.db_file, sep=";", on_bad_lines="warn", encoding="utf-8", engine="python", parse_dates=True, date_parser=pd.to_datetime)


class ColumnSelectionDialog(wx.Dialog):
    def __init__(self, parent: wx.Frame, columns: list):
        super().__init__(parent, title="Select columns to analyze", size=(300, 215))
        self.selected_columns = []

        self.listbox = wx.ListBox(self, choices=columns, style=wx.LB_MULTIPLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.listbox, 1, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), flag=wx.ALIGN_CENTER | wx.ALL, border=15)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.CenterOnParent()

    def on_ok(self, event):
        self.selected_columns = self.listbox.GetSelections()
        if not self.selected_columns:
            wx.MessageBox("Please select at least one column", "Invalid operation", wx.OK | wx.ICON_ERROR)
            return
        self.EndModal(wx.ID_OK)


class SQLiteViewer(wx.Frame):
    """
    A class to display a GUI for viewing SQLite and other databases
    """
    CUSTOM_IDS = {
        "ID_RESIZE_COLUMNS": 1000,
        "ID_RESET_COLUMNS": 1001,
        "ID_DESCRIPTIVE_STATISTICS": 1004,
        "ID_HISTOGRAM": 1005,
        "ID_SCATTER_PLOT": 1006,
        "ID_ANOVA": 1007,
        "ID_REGRESSION_ANALYSIS": 1008,
        "ID_CORRELATION_MATRIX": 1009,
        "ID_BEST_FITTED_DISTRIBUTION": 1010
    }

    def __init__(self):
        super().__init__(None, title="SQLite Viewer: No database loaded", size=(900, 500))
        self.db = None
        self.current_page = None
        self.total_pages = 0
        self.sort_column = None
        self.sort_order = False
        self.search_query = None
        self.items_per_page = 250
        self.create_menu_bar()
        self.create_dashboard()
        self.SetMinSize((450, 350))
        self.Show()

    def create_dashboard(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        self.table_label = wx.StaticText(panel, label="Table name:")
        top_toolbar = wx.BoxSizer(wx.HORIZONTAL)
        self.table_switcher = wx.Choice(panel)
        self.table_switcher.Append("No database loaded")
        self.table_switcher.SetSelection(0)
        self.search_ctrl = wx.SearchCtrl(panel)
        self.search_ctrl.SetDescriptiveText("Search in table")
        self.next_page_button = wx.Button(panel, label="Next page")
        self.next_page_button.Enable(False)
        top_toolbar.AddMany([(self.table_switcher, 0, wx.ALL, 5), (self.search_ctrl, 0, wx.ALL, 5), (self.next_page_button, 0, wx.ALL, 5)])
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT)
        sizer.AddMany([(self.table_label, 0, wx.LEFT | wx.TOP, 5), (top_toolbar, 0, wx.ALL, 0), (self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)])
        self.CreateStatusBar()
        self.bind_events()

    def bind_events(self):
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_auto_size_columns, id=self.CUSTOM_IDS["ID_RESIZE_COLUMNS"])
        self.Bind(wx.EVT_MENU, self.on_reset_columns, id=self.CUSTOM_IDS["ID_RESET_COLUMNS"])
        self.Bind(wx.EVT_MENU, self.on_page_change, id=wx.ID_FORWARD)
        self.Bind(wx.EVT_MENU, self.on_page_change, id=wx.ID_BACKWARD)
        self.Bind(wx.EVT_MENU, self.on_copy, id=wx.ID_COPY)
        self.Bind(wx.EVT_MENU, self.on_select_all, id=wx.ID_SELECTALL)
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_IDS["ID_DESCRIPTIVE_STATISTICS"])
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select_cell)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_select_cell)
        self.table_switcher.Bind(wx.EVT_CHOICE, self.on_switch_table)
        self.next_page_button.Bind(wx.EVT_BUTTON, self.on_page_change)
        self.list_ctrl.Bind(wx.EVT_LIST_COL_CLICK, self.on_column_click)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_search)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.on_search_cancel)

    def create_menu_bar(self):
        menu_bar, file_menu = wx.MenuBar(), wx.Menu()
        file_menu.Append(wx.ID_OPEN, "Open\tCtrl+O", "Open an SQLite file")
        file_menu.Append(wx.ID_EXIT, "Exit\tCtrl+Q", "Exit the application")
        menu_bar.Append(file_menu, "File")

        view_menu, items_per_page_submenu = wx.Menu(), wx.Menu()
        items_per_page_options = [5, 10, 25, 50, 100, 250, 500, 1000]

        for items_per_page in items_per_page_options:
            menu_item = items_per_page_submenu.AppendRadioItem(-1, f"{items_per_page:,} items per page", help=f"Show {items_per_page:,} items per page")
            if items_per_page == self.items_per_page:
                menu_item.Check()
            self.Bind(wx.EVT_MENU, self.on_set_items_per_page, menu_item)

        view_menu.AppendSubMenu(items_per_page_submenu, "Set items per page")
        view_menu.Append(self.CUSTOM_IDS["ID_RESIZE_COLUMNS"], "Auto size columns\tCtrl+Shift+A", "Auto size columns to fit the data")
        view_menu.Append(self.CUSTOM_IDS["ID_RESET_COLUMNS"], "Reset columns", "Reset columns to default order and width")
        view_menu.AppendSeparator()
        view_menu.Append(wx.ID_BACKWARD, "Previous page\tCtrl+Left", "Show the previous page")
        view_menu.Append(wx.ID_FORWARD, "Next page\tCtrl+Right", "Show the next page")
        menu_bar.Append(view_menu, "View")

        select_menu = wx.Menu()
        select_menu.Append(wx.ID_SELECTALL, "Select all\tCtrl+A", "Select all rows")
        select_menu.Append(wx.ID_COPY, "Copy\tCtrl+C", "Copy selected rows to clipboard")
        menu_bar.Append(select_menu, "Select")
        
        data_menu = wx.Menu()
        data_menu.Append(self.CUSTOM_IDS["ID_DESCRIPTIVE_STATISTICS"], "Descriptive statistics", "Show descriptive statistics for a column")
        data_menu.Append(self.CUSTOM_IDS["ID_HISTOGRAM"], "Histogram", "Show a histogram for a column")
        data_menu.Append(self.CUSTOM_IDS["ID_SCATTER_PLOT"], "Scatter plot", "Show a scatter plot for two columns")
        data_menu.Append(self.CUSTOM_IDS["ID_CORRELATION_MATRIX"], "Correlation matrix", "Show a correlation matrix for two or more columns")
        data_menu.Append(self.CUSTOM_IDS["ID_BEST_FITTED_DISTRIBUTION"], "Best fitted distribution", "Show the best fitted distribution for a column")
        data_menu.Append(self.CUSTOM_IDS["ID_REGRESSION_ANALYSIS"], "Regression analysis", "Perform a regression analysis for two or more columns")
        data_menu.Append(self.CUSTOM_IDS["ID_ANOVA"], "ANOVA test", "Perform an ANOVA test for two or more columns")
        menu_bar.Append(data_menu, "Data")

        self.SetMenuBar(menu_bar)

    def load_database_file(self, filename):
        try:
            db = DatabaseConnection(filename)
            table_names = db.get_table_or_sheet_names()
            if not table_names:
                wx.MessageBox("No tables found in database", "Error opening database", wx.OK | wx.ICON_ERROR)
                return
            self.db = db
        except pd.errors.DatabaseError as e:
            wx.MessageBox(f"Error opening database due to \n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self.table_switcher.SetItems(table_names)
        self.table_switcher.SetSelection(0)

        self.column_attr = {}
        self.reset_state()
        self.load_table_data(table_name=table_names[0], page_size=self.items_per_page)
        self.SetTitle(f"SQLite Viewer: Showing database \"{path.basename(filename)}\"")

    def load_table_data(self, table_name: str, page_number: int = 1, page_size: int = 250, sort_column: str = None, sort_order: bool = False, search_query: str = None, set_status: bool = True):
        self.save_column_attr()

        def _worker():
            try:
                df = self.db.get_filtered_sorted_df(table_name=table_name, sort_column=sort_column, sort_order=sort_order, search_query=search_query)
                offset = (page_number - 1) * page_size
                rows = df.iloc[offset:offset+page_size].values.tolist()
                total_rows = len(df.index)
                self.list_ctrl.ShowSortIndicator(col=df.columns.tolist().index(sort_column), ascending=sort_order) if sort_column else self.list_ctrl.RemoveSortIndicator()
            except pd.errors.DatabaseError as e:
                wx.CallAfter(self.list_ctrl.ClearAll)
                wx.CallAfter(self.next_page_button.Enable, False)
                wx.CallAfter(wx.MessageBox, f"Error opening table \"{table_name}\" due to \n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.SetStatusText, "Error opening table")
                return

            if not rows:
                wx.CallAfter(self.list_ctrl.ClearAll)
                wx.CallAfter(self.next_page_button.Enable, False)
                wx.CallAfter(wx.MessageBox, f"No data found in table \"{table_name}\"", "Error displaying table", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.SetStatusText, "No data found in table")
                return

            self.total_pages = math.ceil(total_rows / page_size)
            self.next_page_button.Enable(self.total_pages > 1)
            wx.CallAfter(self.display_table, rows=rows, columns=df.columns.tolist())
            wx.CallAfter(self.SetStatusText, f"Showing table: {table_name}, rows: {total_rows:,}, page: {page_number:,} of {self.total_pages:,}") if set_status else None

        thread = threading.Thread(target=_worker)
        thread.start()
        wx.CallLater(600, lambda: self.progress_dialog(thread=thread) if thread.is_alive() else None)

    def save_column_attr(self):
        previous_table, self.column_attr["current_table"] = self.column_attr.get("current_table"), self.table_switcher.GetStringSelection()
        if previous_table:
            self.column_attr[previous_table] = {
                "col_order": self.list_ctrl.GetColumnsOrder() if self.list_ctrl.GetColumnCount() else None,
                "col_widths": {
                    column: (self.list_ctrl.GetColumnWidth(i)) for i, column in enumerate(
                        [self.list_ctrl.GetColumn(i).GetText() for i in range(self.list_ctrl.GetColumnCount())]
                    )
                }
            }

    def display_table(self, rows: list, columns: list): 
        self.list_ctrl.ClearAll()
        for i, column in enumerate(columns):
            width = self.column_attr.get(self.table_switcher.GetStringSelection(), {}).get("col_widths", {}).get(column, self.list_ctrl.GetTextExtent(column)[0] + 40)
            self.list_ctrl.InsertColumn(i, column, width=width)
        for i, row in enumerate(rows):
            self.list_ctrl.InsertItem(i, str(row[0]))
            for j, cell in enumerate(row[1:], start=1):
                self.list_ctrl.SetItem(i, j, str(cell))
        if column_order := self.column_attr.get(self.table_switcher.GetStringSelection(), {}).get("col_order"):
            self.list_ctrl.SetColumnsOrder(column_order)
        
    def progress_dialog(self, thread: threading.Thread):
        progress_dialog = wx.ProgressDialog("Loading data", "Loading data, please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        while thread.is_alive():
            progress_dialog.Pulse()
        progress_dialog.Destroy()

    def on_open(self, event):
        fd_style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        wildcard = "SQLite files (*.db;*.db3;*.sqlite;*.sqlite3)|*.db;*.db3;*.sqlite;*.sqlite3|Excel files (*.xlsx)|*.xlsx|CSV files (*.csv)|*.csv"
        with wx.FileDialog(self, "Open SQLite file", wildcard=wildcard, style=fd_style) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            self.load_database_file(filename=dlg.GetPath())

    def on_exit(self, event):
        self.Close()

    def on_auto_size_columns(self, event):
        for i in range(self.list_ctrl.GetColumnCount()):
            header = self.list_ctrl.GetColumn(i).GetText()
            width = max(
                self.list_ctrl.GetTextExtent(header)[0] + 40,
                max(
                    self.list_ctrl.GetTextExtent(self.list_ctrl.GetItemText(item, i))[0] + 40
                    for item in range(self.list_ctrl.GetItemCount())
                )
            )  
            self.list_ctrl.SetColumnWidth(i, width)

    def on_reset_columns(self, event):
        if (column_count := self.list_ctrl.GetColumnCount()):
            self.list_ctrl.SetColumnsOrder(list(range(column_count))) 
            for i in range(column_count):
                self.list_ctrl.SetColumnWidth(i, self.list_ctrl.GetTextExtent(self.list_ctrl.GetColumn(i).GetText())[0] + 40)

    def on_copy(self, event):
        data_to_copy = []
        item = self.list_ctrl.GetFirstSelected()
        while item != -1:
            data_to_copy.append([self.list_ctrl.GetItem(item, col).GetText() for col in range(self.list_ctrl.GetColumnCount())])
            item = self.list_ctrl.GetNextSelected(item)

        if data_to_copy:
            clipboard = wx.TextDataObject()
            clipboard.SetText("\n".join(["\t".join(row) for row in data_to_copy]))
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(clipboard)
                wx.TheClipboard.Close()
                self.SetStatusText(f"Copied {(row_count := len(data_to_copy))} row{'s'[:row_count^1]} to clipboard")
            else:
                self.SetStatusText("Error copying to clipboard")
        else:
            self.SetStatusText("No rows selected")

    def on_select_all(self, event):
        for i in range(self.list_ctrl.GetItemCount()):
            self.list_ctrl.Select(i)

    def on_set_items_per_page(self, event):
        self.items_per_page = int(event.GetEventObject().FindItemById(event.GetId()).GetItemLabelText().split(" ")[0].replace(",", ""))
        if self.db:
            self.current_page = 1
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_data_menu(self, event):
        if self.db:
            menu_id = event.GetId()

            if menu_id == self.CUSTOM_IDS["ID_DESCRIPTIVE_STATISTICS"]:
                self.show_column_selection(callback=self.descriptive_statistics)
            elif menu_id == self.CUSTOM_IDS["ID_HISTOGRAM"]:
                self.show_column_selection(self.histogram)
            elif menu_id == self.CUSTOM_IDS["ID_SCATTER_PLOT"]:
                self.show_column_selection(self.scatter_plot)
            elif menu_id == self.CUSTOM_IDS["ID_CORRELATION_MATRIX"]:
                self.show_column_selection(self.correlation_matrix)
            elif menu_id == self.CUSTOM_IDS["ID_BEST_FITTED_DISTRIBUTION"]:
                self.show_column_selection(self.best_fitted_distribution)
            elif menu_id == self.CUSTOM_IDS["ID_REGRESSION_ANALYSIS"]:
                self.show_column_selection(self.regression_analysis)
            elif menu_id == self.CUSTOM_IDS["ID_ANOVA"]:
                self.show_column_selection(self.anova)
        else:
            wx.MessageBox("Unable to perform operation, please load a database first", "Invalid operation", wx.OK | wx.ICON_ERROR)

    def show_column_selection(self, callback: callable):
        df = self.db.get_df(table_name=self.table_switcher.GetStringSelection())
        column_dialog = ColumnSelectionDialog(self, columns=df.columns.tolist())
        if column_dialog.ShowModal() == wx.ID_OK:
            selected_columns = [df.columns[i] for i in column_dialog.selected_columns]
            callback(df=df[selected_columns], columns=selected_columns)

    def descriptive_statistics(self, df: pd.DataFrame, columns: list):
        message = "\n".join([f"{column}:\n{df[column].describe(datetime_is_numeric=True)}\n" for column in columns])
        wx.MessageDialog(self, message, "Descriptive statistics", wx.OK | wx.ICON_INFORMATION).ShowModal()

    def on_column_click(self, event):
        column = self.list_ctrl.GetColumn(event.GetColumn()).GetText()
        if self.sort_column == column:
            if not self.sort_order:
                self.sort_column = None
            self.sort_order = False
        else:
            self.sort_column = column
            self.sort_order = True
        self.current_page = 1
        self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query, set_status=False)
        self.SetStatusText(f"Sorted table by column \"{self.sort_column}\", order: {'ascending' if self.sort_order else 'descending'}" if self.sort_column else "Restored original table order")

    def on_select_cell(self, event):
        self.SetStatusText(f"Selected {(row_count := self.list_ctrl.GetSelectedItemCount())} row{'s'[:row_count^1]}")

    def on_switch_table(self, event):
        if self.db:
            self.reset_state()
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_size=self.items_per_page)

    def on_search(self, event):
        if self.db and (search_query := self.search_ctrl.GetValue()):
            self.current_page, self.search_query = 1, search_query
            self.search_ctrl.ShowCancelButton(True)
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_search_cancel(self, event):
        if self.db:
            self.search_query = None
            self.current_page = 1
            self.search_ctrl.ChangeValue("")
            self.search_ctrl.ShowCancelButton(False)
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_page_change(self, event):
        if self.db and self.total_pages > 1:
            self.current_page = ((self.current_page - 2 if event.GetId() == wx.ID_BACKWARD else self.current_page) % self.total_pages) + 1
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def reset_state(self):
        self.SetStatusText("Processing...")
        self.search_ctrl.ChangeValue("")
        self.search_ctrl.ShowCancelButton(False)
        self.search_query, self.current_page, self.total_pages, self.sort_column, self.sort_order = None, 1, 0, None, False


if __name__ == "__main__":
    app = wx.App()
    SQLiteViewer()
    app.MainLoop()