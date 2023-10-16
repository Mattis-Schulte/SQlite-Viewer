import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import numpy as np
import pandas as pd
import re
import seaborn as sns
import scipy.stats as st
import wx


class ColumnSelectionDialog(wx.Dialog):
    """
    A custom implementation of wx.Dialog to select columns from a listbox

    :param parent: The parent window
    :param columns: A list of columns to display in the listbox
    :param min_count: The minimum number of columns that must be selected
    :param max_count: The maximum number of columns that can be selected
    """
    ignore_filters = True

    def __init__(self, parent: wx.Frame, columns: list, min_count: int = 1, max_count: int | None = None):
        super().__init__(parent, title="Select columns to analyze", size=(300, 225))

        self.min_count, self.max_count = min_count, max_count
        self.listbox = wx.ListBox(self, choices=columns, style=wx.LB_MULTIPLE)
        self.ignore_filters_checkbox = wx.CheckBox(self, label="Ignore applied filters")
        self.ignore_filters_checkbox.SetValue(ColumnSelectionDialog.ignore_filters)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.listbox, 1, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.ignore_filters_checkbox, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), flag=wx.ALIGN_CENTER | wx.ALL, border=15)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_CHECKBOX, self._on_checkbox, self.ignore_filters_checkbox)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.CenterOnParent()

    def _on_checkbox(self, event):
        ColumnSelectionDialog.ignore_filters = self.ignore_filters_checkbox.IsChecked()

    def _on_ok(self, event):
        self.selected_columns = self.listbox.GetSelections()
        if self.min_count and len(self.selected_columns) < self.min_count:
            wx.MessageBox(f"Please select at least {self.min_count} column{'s'[:self.min_count^1]}", "Invalid operation", wx.OK | wx.ICON_ERROR)
            return
        elif self.max_count and len(self.selected_columns) > self.max_count:
            wx.MessageBox(f"Please select no more than {self.max_count} column{'s'[:self.max_count^1]}", "Invalid operation", wx.OK | wx.ICON_ERROR)
            return
        self.EndModal(wx.ID_OK)


class MatplotlibFrame(wx.Frame):
    """
    A custom implementation of wx.Frame to display matplotlib plots
    
    :param parent: The parent window
    """
    SAMPLE_SIZE = 250_000

    def __init__(self, parent):
        super().__init__(parent)

        menubar = wx.MenuBar()
        plot_menu = wx.Menu()
        save_item = plot_menu.Append(wx.ID_SAVE, "Save")
        exit_item = plot_menu.Append(wx.ID_EXIT, "Close")
        menubar.Append(plot_menu, "Plot")
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self._on_save_button, save_item)
        self.Bind(wx.EVT_MENU, self._on_exit_button, exit_item)

    def _configure_plot(self, title: str) -> tuple:
        sns.set_style("darkgrid")
        sns.set_palette("colorblind")
        fig, ax = plt.subplots(figsize=(6, 4))
        canvas = FigureCanvas(self, -1, fig)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(canvas, 1, wx.EXPAND)
        self.SetSizerAndFit(sizer)
        self.SetTitle(f"SQLite Viewer: Showing {title}")
        return fig, ax

    def _sample_data(self, df: pd.DataFrame, sample_size: int, ax: plt.Axes) -> pd.DataFrame:
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=1)
            ax.text(0.05, 0.95, f"Sampled {sample_size:,} rows", transform=ax.transAxes, fontsize=12, verticalalignment="top", horizontalalignment="left", bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        return df
    
    def _draw_plot(self, fig: plt.Figure, ax: plt.Axes):
        plt.tight_layout()
        canvas = FigureCanvas(self, -1, fig)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(canvas, 1, wx.EXPAND)
        self.SetSizerAndFit(sizer)
        canvas.draw()

    def _save_plot(self, file_path: str):
        if not file_path.lower().endswith((".png", ".jpg")):
            file_path += ".png"
        plt.savefig(file_path, bbox_inches="tight")

    def _on_save_button(self, event):
        default_file = f"{self.title.lower().replace(' ', '-')}.png" if self.title else ""
        default_file = re.sub(r"[<>:\"/\\|?*]", "", default_file)
        with wx.FileDialog(self, "Save Plot", defaultFile=default_file, wildcard="Image files (*.png;*.jpg)|*.png;*.jpg", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL: 
                return
            self._save_plot(file_path=file_dialog.GetPath())

    def _on_exit_button(self, event):
        self.Destroy()

    def plot_histogram(self, df: pd.DataFrame, columns: list, dist_names: list[str, ...] | None = None, params: list[tuple, ...] | None = None):
        """
        Plots a histogram of the specified columns and optionally the best fitted distribution too

        :param df: The dataframe to plot the histogram for
        :param columns: The columns to plot the histogram for
        :param dist_names: The names of the distributions to plot
        :param params: The parameters of the distributions to plot
        """
        self.title = f"{'Best Fitted Distribution' if dist_names else 'Histogram'} \"{', '.join(columns)}\""
        fig, ax = self._configure_plot(self.title)

        df = self._sample_data(df, self.SAMPLE_SIZE, ax)
        hist_data = pd.concat([df[graph] for graph in columns])
        log_scale_x = bool(abs(hist_data.skew()) > 2) if hist_data.dtype.kind in "biufc" else False
        
        for i, graph in enumerate(columns):
            sns.histplot(data=df, x=graph, ax=ax, stat="density", bins="auto", log_scale=log_scale_x, label=graph)   
            if dist_names and params and i < min(len(dist_names), len(params)):
                param_names = [name.strip() for name in getattr(st, dist_names[i]).shapes.split(",")] if getattr(st, dist_names[i]).shapes else []
                param_names += ['loc'] if dist_names[i] in st._discrete_distns._distn_names else ['loc', 'scale']
                param_str = ", ".join([f"{param_name}: {param:.2f}" for param_name, param in zip(param_names, params[i])])

                if log_scale_x:
                    shift = abs(df[graph].min()) + 1 if df[graph].min() < 0 else 0
                    x = np.logspace(np.log10(shift + df[graph].min()), np.log10(shift + df[graph].max()), 1000)
                    pdf = getattr(st, dist_names[i]).pdf(x, *params[i])
                    # TODO: Fix y-axis scaling for log scale
                else:
                    x = np.linspace(df[graph].min(), df[graph].max(), 1000)
                    pdf = getattr(st, dist_names[i]).pdf(x, *params[i])
                
                plt.autoscale(False)
                line_color = sns.color_palette("dark", n_colors=len(columns))[i]
                ax.plot(x, pdf, label=f"{dist_names[i]} ({param_str})", color=line_color, linestyle="dashed")
        
        ax.set_xlabel(f"{columns[0] if len(columns) == 1 else ' '}{' (log scale)' if log_scale_x else ''}")
        ax.legend(loc="lower left") if len(ax.get_legend_handles_labels()[0]) > 1 else ax.legend().remove()
        self._draw_plot(fig, ax)

    def plot_scatter(self, df: pd.DataFrame, column_combinations: list, regression_line: bool = False, regression_line_params: tuple | None = None):
        """
        Plots a scatter plot for the specified column combinations

        :param df: The dataframe to plot
        :param column_combinations: The column combinations to plot as a nested list with the inner lists containing a pair of columns
        :param regression_line: Whether to plot a regression lines
        :param regression_line_params: The parameters of the regression line (slope, intercept, rvalue, pvalue, stderr), only displayed if there is one column combination
        """
        self.title = f"Scatter Plot \"{', '.join([' / '.join(graph) for graph in column_combinations])}\""
        fig, ax = self._configure_plot(self.title)

        df = self._sample_data(df, self.SAMPLE_SIZE, ax)
        scatter_data_x = pd.concat([df[graph[0]] for graph in column_combinations])
        scatter_data_y = pd.concat([df[graph[1]] for graph in column_combinations])
        scatter_log_scale_x = bool(abs(scatter_data_x.skew()) > 2) if scatter_data_x.dtype.kind in "biufc" else False
        scatter_log_scale_y = bool(abs(scatter_data_y.skew()) > 2) if scatter_data_y.dtype.kind in "biufc" else False
        
        for i, graph in enumerate(column_combinations):
            sns.scatterplot(data=df, x=graph[0], y=graph[1], ax=ax, label=f"{graph[0]} / {graph[1]}")
            if regression_line:
                line_color = sns.color_palette("dark", n_colors=len(column_combinations))[i]
                sns.regplot(data=df, x=graph[0], y=graph[1], ax=ax, scatter=False, color=line_color, label=f"{graph[0]} / {graph[1]}")
                if regression_line_params and len(column_combinations) == 1:
                    text_result = f"Slope: {regression_line_params.slope:.4f}\nIntercept: {regression_line_params.intercept:.4f}\nR-value: {regression_line_params.rvalue:.4f}\nP-value: {regression_line_params.pvalue:.4f}\nStandard error: {regression_line_params.stderr:.4f}"
                    ax.text(0.95, 0.95, text_result, transform=ax.transAxes, fontsize=12, verticalalignment="top", horizontalalignment="right", bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        plt.xscale("log") if scatter_log_scale_x else None
        plt.yscale("log") if scatter_log_scale_y else None
        ax.set_xlabel(f"{', '.join([graph[0] for graph in column_combinations])}{' (log scale)' if scatter_log_scale_x else ''}")
        ax.set_ylabel(f"{', '.join([graph[1] for graph in column_combinations])}{' (log scale)' if scatter_log_scale_y else ''}")
        ax.legend(loc="lower left") if len(ax.get_legend_handles_labels()[0]) > 1 else ax.legend().remove()
        self._draw_plot(fig, ax)

    def plot_correlation_matrix(self, df: pd.DataFrame, columns: list):
        """
        Plots a correlation matrix for the specified columns

        :param df: The dataframe to plot
        :param columns: The names of the columns to plot as a list
        """
        self.title = f"Correlation Matrix \"{', '.join(columns)}\""
        fig, ax = self._configure_plot(self.title)
        sns.heatmap(data=df[columns].corr(numeric_only=False), annot=True, fmt=".2f", ax=ax)
        self._draw_plot(fig, ax)
