import math
import matplotlib.pyplot as plt
import os.path as path
import pandas as pd
import scipy.stats as st
from threading import Event
from concurrent.futures import ThreadPoolExecutor, Future
from utils.database_handler import DataframeConnection
from utils.custom_wx_objects import ColumnSelectionDialog, MatplotlibFrame
import warnings
import wx


class SQLiteViewer(wx.Frame):
    """
    A class to display a GUI for viewing SQLite and other databases
    """
    CUSTOM_BIND_IDS = {
        "ID_RESIZE_COLUMNS": 1000,
        "ID_RESET_COLUMNS": 1001,
        "ID_DESCRIPTIVE_STATISTICS": 1004,
        "ID_HISTOGRAM": 1005,
        "ID_SCATTER_PLOT": 1006,
        "ID_CORRELATION_MATRIX": 1007,
        "ID_BEST_FITTED_DISTRIBUTION": 1008,
        "ID_REGRESSION_ANALYSIS": 1009,
        "ID_ANOVA": 1010
    }

    def __init__(self):
        super().__init__(None, title="SQLite Viewer: No database loaded", size=(900, 500))
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")
        self.db = None
        self.current_page = 1
        self.total_pages = 0
        self.sort_column = None
        self.sort_order = False
        self.search_query = None
        self.items_per_page = 250
        self.main_executor = ThreadPoolExecutor(max_workers=1)
        self.secondary_executor = ThreadPoolExecutor()
        self.list_ctrl_loading_thread = None
        self.load_table_data_flag = Event()
        self.create_menu_bar()
        self.create_dashboard()
        self.SetMinSize((450, 350))
        self.Show()

    def create_dashboard(self):
        """
        Creates the main dashboard for the application
        """
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
        """
        Binds events to the controls on the dashboard and the menu bar
        """
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_auto_size_columns, id=self.CUSTOM_BIND_IDS["ID_RESIZE_COLUMNS"])
        self.Bind(wx.EVT_MENU, self.on_reset_columns, id=self.CUSTOM_BIND_IDS["ID_RESET_COLUMNS"])
        self.Bind(wx.EVT_MENU, self.on_page_change, id=wx.ID_FORWARD)
        self.Bind(wx.EVT_MENU, self.on_page_change, id=wx.ID_BACKWARD)
        self.Bind(wx.EVT_MENU, self.on_copy, id=wx.ID_COPY)
        self.Bind(wx.EVT_MENU, self.on_select_all, id=wx.ID_SELECTALL)
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_DESCRIPTIVE_STATISTICS"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_HISTOGRAM"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_SCATTER_PLOT"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_CORRELATION_MATRIX"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_BEST_FITTED_DISTRIBUTION"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_REGRESSION_ANALYSIS"])
        self.Bind(wx.EVT_MENU, self.on_data_menu, id=self.CUSTOM_BIND_IDS["ID_ANOVA"])
        self.Bind(wx.EVT_CLOSE, self.on_exit)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select_cell)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_select_cell)
        self.table_switcher.Bind(wx.EVT_CHOICE, self.on_switch_table)
        self.next_page_button.Bind(wx.EVT_BUTTON, self.on_page_change)
        self.list_ctrl.Bind(wx.EVT_LIST_COL_CLICK, self.on_column_click)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_search)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.on_search_cancel)

    def create_menu_bar(self):
        """
        Creates the menu bar for the application
        """
        menu_bar, file_menu = wx.MenuBar(), wx.Menu()
        file_menu.Append(wx.ID_OPEN, "Open\tCtrl+O", "Open an SQLite file")
        file_menu.Append(wx.ID_EXIT, "Exit\tCtrl+Q", "Exit the application")
        menu_bar.Append(file_menu, "File")

        view_menu, items_per_page_submenu = wx.Menu(), wx.Menu()
        items_per_page_options = (5, 10, 25, 50, 100, 250, 500, 1000)

        for items_per_page in items_per_page_options:
            menu_item = items_per_page_submenu.AppendRadioItem(-1, f"{items_per_page:,} items per page", help=f"Show {items_per_page:,} items per page")
            if items_per_page == self.items_per_page:
                menu_item.Check()
            self.Bind(wx.EVT_MENU, self.on_set_items_per_page, menu_item)

        view_menu.AppendSubMenu(items_per_page_submenu, "Set items per page")
        view_menu.Append(self.CUSTOM_BIND_IDS["ID_RESIZE_COLUMNS"], "Auto size columns\tCtrl+Shift+A", "Auto size columns to fit the data")
        view_menu.Append(self.CUSTOM_BIND_IDS["ID_RESET_COLUMNS"], "Reset columns", "Reset columns to default order and width")
        view_menu.AppendSeparator()
        view_menu.Append(wx.ID_BACKWARD, "Previous page\tCtrl+Left", "Show the previous page")
        view_menu.Append(wx.ID_FORWARD, "Next page\tCtrl+Right", "Show the next page")
        menu_bar.Append(view_menu, "View")

        select_menu = wx.Menu()
        select_menu.Append(wx.ID_SELECTALL, "Select all\tCtrl+A", "Select all rows")
        select_menu.Append(wx.ID_COPY, "Copy\tCtrl+C", "Copy selected rows to clipboard")
        menu_bar.Append(select_menu, "Select")
        
        data_menu = wx.Menu()
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_DESCRIPTIVE_STATISTICS"], "Descriptive statistics", "Show descriptive statistics for one or more columns")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_HISTOGRAM"], "Histogram", "Show a histogram for one or more columns")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_SCATTER_PLOT"], "Scatter plot", "Show a scatter plot for two columns")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_CORRELATION_MATRIX"], "Correlation matrix", "Show a Pearson correlation matrix for two or more columns")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_BEST_FITTED_DISTRIBUTION"], "Best fitted distribution", "Show the best fitted distribution for a column")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_REGRESSION_ANALYSIS"], "Regression analysis", "Perform a regression analysis for two or more columns")
        data_menu.Append(self.CUSTOM_BIND_IDS["ID_ANOVA"], "ANOVA test", "Perform an ANOVA test for two or more columns")
        menu_bar.Append(data_menu, "Data")

        self.SetMenuBar(menu_bar)

    def load_database_file(self, file_path):
        """
        Tries to load the specified database file and displays an error message if it fails

        :param file_path: The path to the database file
        """
        try:
            db = DataframeConnection(db_file=file_path)
            table_names = db.get_table_or_sheet_names()
            if not table_names:
                wx.MessageBox("No tables found in database", "Error opening database", wx.OK | wx.ICON_ERROR)
                return
            self.db = db
        except Exception as e:
            wx.MessageBox(f"Error opening database due to:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            raise e
        self.table_switcher.SetItems(table_names)
        self.table_switcher.SetSelection(0)

        for child in self.GetChildren():
            if isinstance(child, MatplotlibFrame):
                child.Close()
        
        self.column_attr = {}
        self.reset_state()
        self.load_table_data(table_name=table_names[0], page_size=self.items_per_page)
        self.SetTitle(f"SQLite Viewer: Showing database \"{path.basename(file_path)}\"")

    def load_table_data(self, table_name: str, page_number: int = 1, page_size: int = 250, sort_column: str | None = None, sort_order: bool = False, search_query: str | None = None, set_status: bool = True):
        """
        Prepares the dataframes for the specified table and loads the first page, for performance reasons within a separate thread

        :param table_name: The name of the table to load
        :param page_number: The page number to load
        :param page_size: The number of rows to load per page
        :param sort_column: The name of the column to sort by
        :param sort_order: The order to sort by, True for ascending, False for descending (ignored if sort_column is None)
        :param search_query: The string to search for in the dataframe
        :param set_status: Whether to update the status bar text
        """
        def _worker():
            self.save_column_attr(table_name=table_name)
            
            try:
                df = self.db.get_filtered_sorted_df(table_name=table_name, sort_column=sort_column, sort_order=sort_order, search_query=search_query)
                offset = (page_number - 1) * page_size
                rows = df.iloc[offset:offset+page_size].values.tolist()
                total_rows = len(df.index)
                self.total_pages = math.ceil(total_rows / page_size)
            except Exception as e:
                wx.CallAfter(self.list_ctrl.ClearAll)
                wx.CallAfter(self.next_page_button.Enable, False)
                wx.CallAfter(wx.MessageBox, f"Error opening table \"{table_name}\" due to:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.SetStatusText, "Error opening table")
                raise e

            if not rows:
                wx.CallAfter(self.list_ctrl.ClearAll)
                wx.CallAfter(self.next_page_button.Enable, False)
                wx.CallAfter(wx.MessageBox, f"No data found in table \"{table_name}\"", "Error displaying table", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.SetStatusText, "No data found in table")
                return

            wx.CallAfter(self.next_page_button.Enable, self.total_pages > 1)
            wx.CallAfter(self.list_ctrl.ShowSortIndicator, col=df.columns.tolist().index(sort_column), ascending=sort_order) if sort_column else wx.CallAfter(self.list_ctrl.RemoveSortIndicator)
            wx.CallAfter(self.SetStatusText, f"Showing table: {table_name}, rows: {total_rows:,}, page: {page_number:,} of {self.total_pages:,}") if set_status else None
            wx.CallAfter(self.display_table, table_name=table_name, rows=rows, columns=df.columns.tolist())

        if self.list_ctrl_loading_thread is not None and not self.list_ctrl_loading_thread.done():
            if not self.list_ctrl_loading_thread.cancel():
                self.load_table_data_flag.set()
        
        self.list_ctrl_loading_thread = self.main_executor.submit(_worker)
        wx.CallLater(600, lambda: self.progress_dialog(future=self.list_ctrl_loading_thread) if not self.list_ctrl_loading_thread.done() else None)

    def save_column_attr(self, table_name: str):
        """
        Gets and saves the current column order and widths for the selected table in self.column_attr

        :param table_name: The name of the table to save the column order and widths for
        """
        previous_table, self.column_attr["current_table"] = self.column_attr.get("current_table"), table_name
        if previous_table:
            self.column_attr[previous_table] = {
                "col_order": self.list_ctrl.GetColumnsOrder() if self.list_ctrl.GetColumnCount() else None,
                "col_widths": {
                    column: (self.list_ctrl.GetColumnWidth(i)) for i, column in enumerate(
                        [self.list_ctrl.GetColumn(i).GetText() for i in range(self.list_ctrl.GetColumnCount())]
                    )
                }
            }

    def display_table(self, table_name: str, rows: list, columns: list):
        """
        Displays the specified rows and columns in the list control and applies the column order and widths if they exist in self.column_attr

        :param table_name: The name of the table to display
        :param rows: The rows to display
        :param columns: The columns to display
        """
        self.list_ctrl.ClearAll()
        for i, column in enumerate(columns):
            width = self.column_attr.get(table_name, {}).get("col_widths", {}).get(column, self.list_ctrl.GetTextExtent(column)[0] + 40)
            self.list_ctrl.InsertColumn(i, column, width=width)
        for i, row in enumerate(rows):
            self.list_ctrl.InsertItem(i, str(row[0]))
            for j, cell in enumerate(row[1:], start=1):
                if self.load_table_data_flag.is_set():
                    self.load_table_data_flag.clear()
                    return
                self.list_ctrl.SetItem(i, j, str(cell))
        if column_order := self.column_attr.get(table_name, {}).get("col_order"):
            self.list_ctrl.SetColumnsOrder(orders=column_order)

    def progress_dialog(self, future: Future):
        """
        Displays a progress dialog while the specified future is running

        :param future: The future to display a progress dialog for
        """
        progress_dialog = wx.ProgressDialog("Processing data", "Processing data, please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        while future.running():
            progress_dialog.Pulse()
        progress_dialog.Destroy()

    def on_open(self, event):
        """
        Opens a file dialog to select a database file to open
        """
        fd_style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        wildcard = "SQLite files (*.db;*.db3;*.sqlite;*.sqlite3)|*.db;*.db3;*.sqlite;*.sqlite3|Excel files (*.xlsx)|*.xlsx|CSV files (*.csv)|*.csv"
        with wx.FileDialog(self, "Open SQLite file", wildcard=wildcard, style=fd_style) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            self.load_database_file(file_path=dlg.GetPath())

    def on_exit(self, event):
        """
        Exits the application and makes sure all matplotlib figures are closed as well
        """
        plt.close("all")
        self.Destroy()

    def on_auto_size_columns(self, event):
        """
        Auto sizes the columns to fit the data
        """
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
        """
        Resets the columns back to their default order and width
        """
        if (column_count := self.list_ctrl.GetColumnCount()):
            self.list_ctrl.SetColumnsOrder(list(range(column_count))) 
            for i in range(column_count):
                self.list_ctrl.SetColumnWidth(i, self.list_ctrl.GetTextExtent(self.list_ctrl.GetColumn(i).GetText())[0] + 40)

    def on_copy(self, event):
        """
        Copies the selected rows to the clipboard as tab separated values with a newline between each row to allow pasting into Excel
        """
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
        """
        Selects all rows in the list control
        """
        for i in range(self.list_ctrl.GetItemCount()):
            self.list_ctrl.Select(i)

    def on_set_items_per_page(self, event):
        """
        Changes the number of items that are displayed per page to the selected value
        """
        self.items_per_page = int(event.GetEventObject().FindItemById(event.GetId()).GetItemLabelText().split(" ")[0].replace(",", ""))
        if self.db and self.list_ctrl.GetColumnCount():
            self.current_page = 1
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_data_menu(self, event):
        """
        Wrapper function for the data analysis menu items
        """
        if self.db and self.list_ctrl.GetColumnCount():
            menu_id = event.GetId()

            if menu_id == self.CUSTOM_BIND_IDS["ID_DESCRIPTIVE_STATISTICS"]:
                self.show_column_selection_dialog(callback=self.on_descriptive_statistics)
            elif menu_id == self.CUSTOM_BIND_IDS["ID_HISTOGRAM"]:
                self.show_column_selection_dialog(callback=self.on_histogram, valid_dtypes=["number", "datetime"])
            elif menu_id == self.CUSTOM_BIND_IDS["ID_SCATTER_PLOT"]:
                self.show_column_selection_dialog(callback=self.on_scatter_plot, valid_dtypes=["number", "datetime"], min_column_count=2, max_column_count=2)
            elif menu_id == self.CUSTOM_BIND_IDS["ID_CORRELATION_MATRIX"]:
                self.show_column_selection_dialog(callback=self.on_correlation_matrix, valid_dtypes=["number", "datetime"], min_column_count=2, min_data_count=10)
            elif menu_id == self.CUSTOM_BIND_IDS["ID_BEST_FITTED_DISTRIBUTION"]:
                self.show_column_selection_dialog(callback=self.on_best_fitted_distribution, valid_dtypes=["number"], min_column_count=1, max_column_count=1, min_data_count=10)
            elif menu_id == self.CUSTOM_BIND_IDS["ID_REGRESSION_ANALYSIS"]:
                self.show_column_selection_dialog(callback=self.on_regression_analysis, valid_dtypes=["number"], min_column_count=2, min_data_count=10)
            elif menu_id == self.CUSTOM_BIND_IDS["ID_ANOVA"]:
                self.show_column_selection_dialog(callback=self.on_anova, valid_dtypes=["number", "datetime"], min_column_count=2, min_data_count=10)
        else:
            wx.MessageBox("Unable to perform operation, please load a valid table first", "Invalid operation", wx.OK | wx.ICON_ERROR)

    def show_column_selection_dialog(self, callback: callable, valid_dtypes: list | None = None, min_column_count: int = 1, max_column_count: int | None = None, min_data_count: int = 1):
        """
        Shows a dialog to select columns for the specified data analysis

        :param callback: The function to call with the selected columns
        :param valid_dtypes: The valid data types for the columns to select
        :param min_column_count: The minimum number of columns to select
        :param max_column_count: The maximum number of columns to select
        :param min_data_count: The minimum number of data rows required to perform the analysis
        """
        df = self.db.get_df(table_name=self.table_switcher.GetStringSelection())
        columns = [col for col in df.select_dtypes(include=valid_dtypes).columns.tolist() if df[col].isna().sum() != len(df)] if valid_dtypes else df.columns.tolist()
        columns = [col for col in [self.list_ctrl.GetColumn(i).GetText() for i in self.list_ctrl.GetColumnsOrder()] if col in columns]
        
        if len(columns) < min_column_count:
            wx.MessageBox(f"Unable to perform operation, please load a table with at least {min_column_count} valid column{'s'[:min_column_count^1]}", "Invalid operation", wx.OK | wx.ICON_ERROR)
            return
        
        column_dialog = ColumnSelectionDialog(parent=self, columns=columns, min_count=min_column_count, max_count=max_column_count)
        if column_dialog.ShowModal() == wx.ID_OK:
            selected_columns = [columns[i] for i in column_dialog.selected_columns]
            if not column_dialog.ignore_filters:
                df = self.db.get_filtered_sorted_df(table_name=self.table_switcher.GetStringSelection(), sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)
            if len(df) < min_data_count:
                wx.MessageBox(f"Unable to perform operation, please load a table with at least {min_data_count:,} rows", "Invalid operation", wx.OK | wx.ICON_ERROR)
                return
            callback(df=df[selected_columns], columns=selected_columns)
        column_dialog.Destroy()

    def on_descriptive_statistics(self, df: pd.DataFrame, columns: list):
        """
        Shows descriptive statistics for the specified columns

        :param df: The dataframe to analyze
        :param columns: The names of the columns to analyze as a list
        """
        message = "\n".join([f"{column}:\n{df[column].describe(datetime_is_numeric=True)}\n" for column in columns])
        wx.MessageBox(message, "Descriptive statistics", wx.OK | wx.ICON_INFORMATION)

    def on_histogram(self, df: pd.DataFrame, columns: list):
        """
        Shows a histogram for the specified columns

        :param df: The dataframe to plot
        :param columns: The names of the columns to plot as a list
        """
        if not (any(df[graph].dtype != "datetime64[ns]" for graph in columns) and any(df[graph].dtype == "datetime64[ns]" for graph in columns)):
            frame = MatplotlibFrame(parent=self)
            frame.plot_histogram(df=df, columns=columns)
            frame.Show()
        else:
            wx.MessageBox("Unable to plot a histogram for a mix of numerical and datetime columns", "Invalid operation", wx.OK | wx.ICON_ERROR)
   
    def on_scatter_plot(self, df: pd.DataFrame, columns: list):
        """
        Shows a scatter plot for the specified column combinations

        :param df: The dataframe to plot
        :param columns: The names of the column combination to plot
        """
        frame = MatplotlibFrame(parent=self)
        frame.plot_scatter(df=df, column_combinations=[[columns[0], columns[1]]])
        frame.Show()

    def on_correlation_matrix(self, df: pd.DataFrame, columns: list):
        """
        Shows a correlation matrix for the specified columns

        :param df: The dataframe to analyze
        :param columns: The names of the columns to analyze as a list
        """
        frame = MatplotlibFrame(parent=self)
        frame.plot_correlation_matrix(df=df, columns=columns)
        frame.Show()

    def on_best_fitted_distribution(self, df: pd.DataFrame, columns: list):
        """
        Shows the best fitted distribution for the specified column

        :param df: The dataframe to analyze
        :param columns: The name of the column to analyze
        """
        def _show_best_fitted_distribution(df: pd.DataFrame, columns: list, dist_names: list, params: list):
            frame = MatplotlibFrame(parent=self)
            frame.plot_histogram(df=df, columns=columns, dist_names=dist_names, params=params)
            frame.Show()

        def _worker():
            dist_names = ("norm", "expon", "pareto", "lognorm", "gamma", "beta", "uniform", "dweibull")
            best_dist, best_params, best_aic = None, None, math.inf
            
            try:
                data = df[columns[0]].dropna()
                for dist_name in dist_names:
                    params = getattr(st, dist_name).fit(data)
                    ll = getattr(st, dist_name).logpdf(data, *params).sum()
                    aic = 2 * len(params) - 2 * ll

                    if aic < best_aic:
                        best_aic, best_dist, best_params = aic, dist_name, params

                wx.CallAfter(_show_best_fitted_distribution, df=df, columns=columns, dist_names=[best_dist], params=[best_params])
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"Error finding best fitted distribution due to:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
                raise e

        loading_thread = self.secondary_executor.submit(_worker)
        wx.CallLater(600, lambda: self.progress_dialog(future=loading_thread) if not loading_thread.done() else None)

    def on_regression_analysis(self, df: pd.DataFrame, columns: list):
        """
        Performs a regression analysis for the specified columns

        :param df: The dataframe to analyze
        :param columns: The names of the columns to analyze as a list
        """
        try:
            min_len = min(len(df[column].dropna().values) for column in columns)
            data = [df[column].dropna().values[:min_len] for column in columns]
            result = st.linregress(*data)

            frame = MatplotlibFrame(parent=self)
            frame.plot_scatter(df=df, column_combinations=[[columns[0], columns[1]]], regression_line=True, regression_line_params=result)
            frame.Show()
        except Exception as e:
            wx.MessageBox(f"Error performing regression analysis due to:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            raise e

    def on_anova(self, df: pd.DataFrame, columns: list):
        """
        Performs an ANOVA test for the specified columns

        :param df: The dataframe to analyze
        :param columns: The names of the columns to analyze as a list
        """
        try:
            data = [df[column].dropna().values for column in columns]
            result = st.f_oneway(*data)
            wx.MessageBox(f"ANOVA test results:\nF-statistic: {result.statistic:.4f}\nP-value: {result.pvalue:.4f}", "ANOVA test results", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error performing ANOVA test due to:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            raise e

    def on_column_click(self, event):
        """
        Sorts the table by the clicked column toggling between ascending, descending and the original order
        """
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
        """
        Updates the status bar with the number of selected rows
        """
        self.SetStatusText(f"Selected {(row_count := self.list_ctrl.GetSelectedItemCount())} row{'s'[:row_count^1]}")

    def on_switch_table(self, event):
        """
        Switches to the selected table
        """
        if self.db:
            self.reset_state()
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_size=self.items_per_page)

    def on_search(self, event):
        """
        Reloads the table with the search query applied
        """
        if self.db and (search_query := self.search_ctrl.GetValue()):
            self.current_page, self.search_query = 1, search_query
            self.search_ctrl.ShowCancelButton(True)
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_search_cancel(self, event):
        """
        Reloads the table with the search query removed
        """
        if self.db:
            self.search_query = None
            self.current_page = 1
            self.search_ctrl.ChangeValue("")
            self.search_ctrl.ShowCancelButton(False)
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def on_page_change(self, event):
        """
        Loads the next or previous page while wrapping around if necessary
        """
        if self.db and self.total_pages > 1:
            self.current_page = ((self.current_page - 2 if event.GetId() == wx.ID_BACKWARD else self.current_page) % self.total_pages) + 1
            self.load_table_data(table_name=self.table_switcher.GetStringSelection(), page_number=self.current_page, page_size=self.items_per_page, sort_column=self.sort_column, sort_order=self.sort_order, search_query=self.search_query)

    def reset_state(self):
        """
        Resets the state of the application to a semi default state
        """
        self.SetStatusText("Processing...")
        self.search_ctrl.ChangeValue("")
        self.search_ctrl.ShowCancelButton(False)
        self.search_query, self.current_page, self.total_pages, self.sort_column, self.sort_order = None, 1, 0, None, False


if __name__ == "__main__":
    app = wx.App()
    SQLiteViewer()
    app.MainLoop()
