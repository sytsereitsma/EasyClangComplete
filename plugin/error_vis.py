"""Module for compile error visualization.

Attributes:
    log (logging): this module logger
"""
import logging
import sublime
from os import path

from .completion.compiler_variant import LibClangCompilerVariant

log = logging.getLogger(__name__)


class CompileErrors:
    """Comple errors is a class that encapsulates compile error visualization.

    Attributes:
        err_regions (dict): dictionary of error regions for view ids
    """

    _TAG = "easy_clang_complete_errors"
    _MAX_POPUP_WIDTH = 1800

    err_regions = {}
    phantom_sets = {}

    HTML_STYLE_MASK = """
<style>
html {{
  background-color: {background_color};
  color: {text_color};
}}
</style>
"""

    def generate(self, view, errors):
        """Generate a dictionary that stores all errors.

        The errors are stored along with their positions and descriptions.
        Needed to show these errors on the screen.

        Args:
            view (sublime.View): current view
            errors (list): list of parsed errors (dict objects)
        """
        view_id = view.buffer_id()
        if view_id == 0:
            log.error(" trying to show error on invalid view. Abort.")
            return
        log.debug(" generating error regions for view %s", view_id)
        # first clear old regions
        if view_id in self.err_regions:
            log.debug(" removing old error regions")
            del self.err_regions[view_id]
        # create an empty region dict for view id
        self.err_regions[view_id] = {}

        # If the view is closed while this is running, there will be
        # errors. We want to handle them gracefully.
        try:
            for error in errors:
                self.add_error(view, error)
            log.debug(" %s error regions ready", len(self.err_regions))
        except (AttributeError, KeyError, TypeError) as e:
            log.error(" view was closed -> cannot generate error vis in it")
            log.info(" original exception: '%s'", repr(e))

    def add_error(self, view, error_dict):
        """Put new compile error in the dictionary of errors.

        Args:
            view (sublime.View): current view
            error_dict (dict): current error dict {row, col, file, region}
        """
        logging.debug(" adding error %s", error_dict)
        error_source_file = path.basename(error_dict['file'])
        if error_source_file == path.basename(view.file_name()):
            row = int(error_dict['row'])
            col = int(error_dict['col'])
            point = view.text_point(row - 1, col - 1)
            error_dict['region'] = view.word(point)
            if row in self.err_regions[view.buffer_id()]:
                self.err_regions[view.buffer_id()][row] += [error_dict]
            else:
                self.err_regions[view.buffer_id()][row] = [error_dict]

    def show_phantoms(self, view):
        """Show phantoms for compilation errors.

        Args:
            view (sublime.View): current view
        """
        view.erase_phantoms("compile_errors")
        if view.buffer_id() not in self.phantom_sets:
            phantom_set = sublime.PhantomSet(view, "compile_errors")
            self.phantom_sets[view.buffer_id()] = phantom_set
        else:
            phantom_set = self.phantom_sets[view.buffer_id()]
        phantoms = []
        current_error_dict = self.err_regions[view.buffer_id()]
        for err in current_error_dict:
            errors_dict = current_error_dict[err]
            errors_html = CompileErrors._as_phantom_html(errors_dict)
            pt = view.text_point(err - 1, 1)
            phantoms.append(sublime.Phantom(
                sublime.Region(pt, view.line(pt).b),
                errors_html,
                sublime.LAYOUT_BELOW,
                on_navigate=self._on_phantom_navigate))
        phantom_set.update(phantoms)

    def show_regions(self, view, show_phantoms):
        """Show current error regions.

        Args:
            view (sublime.View): Current view
        """
        if view.buffer_id() not in self.err_regions:
            # view has no errors for it
            return
        current_error_dict = self.err_regions[view.buffer_id()]
        regions = CompileErrors._as_region_list(current_error_dict)
        log.debug(" showing error regions: %s", regions)
        view.add_regions(CompileErrors._TAG, regions, "code")
        if show_phantoms:
            self.show_phantoms(view)

    def erase_regions(self, view):
        """Erase error regions for view.

        Args:
            view (sublime.View): erase regions for view
        """
        if view.buffer_id() not in self.err_regions:
            # view has no errors for it
            return
        log.debug(" erasing error regions for view %s", view.buffer_id())
        view.erase_regions(CompileErrors._TAG)

    def show_popup_if_needed(self, view, row):
        """Show a popup if it is needed in this row.

        Args:
            view (sublime.View): current view
            row (int): number of row
        """
        if view.buffer_id() not in self.err_regions:
            return
        current_err_region_dict = self.err_regions[view.buffer_id()]
        if row in current_err_region_dict:
            errors_dict = current_err_region_dict[row]
            errors_html = CompileErrors._as_html(errors_dict)
            view.show_popup(errors_html, max_width=self._MAX_POPUP_WIDTH)
        else:
            log.debug(" no error regions for row: %s", row)

    def clear(self, view):
        """Clear errors from dict for view.

        Args:
            view (sublime.View): current view
        """
        if view.buffer_id() not in self.err_regions:
            # no errors for this view
            return
        view.hide_popup()
        self.erase_regions(view)
        self.err_regions[view.buffer_id()].clear()

    def remove_region(self, view_id, row):
        """Remove a region for view_id in row.

        Args:
            view_id (int): view id
            row (int): row number
        """
        if view_id not in self.err_regions:
            # no errors for this view
            return
        current_error_dict = self.err_regions[view_id]
        if row not in current_error_dict:
            # no errors for this row
            return
        del current_error_dict[row]

    @staticmethod
    def _on_phantom_navigate(self):
        """Close all phantoms in active view.

        """
        sublime.active_window().active_view().erase_phantoms("compile_errors")

    @staticmethod
    def _as_html(errors_dict):
        """Show error as html.

        Args:
            errors_dict (dict): Current error
        """
        errors_html = ""
        for entry in errors_dict:
            processed_error = entry['error']
            processed_error = processed_error.replace(' ', '&nbsp;')
            processed_error = processed_error.replace('<', '&lt;')
            processed_error = processed_error.replace('>', '&gt;')
            if LibClangCompilerVariant.SEVERITY_TAG in entry:
                severity = entry[LibClangCompilerVariant.SEVERITY_TAG]
                if severity > 2:
                    errors_html = CompileErrors.HTML_STYLE_MASK.format(
                        background_color="#BB2222", text_color="#EEEEEE")
                    errors_html += "<b>Error:</b><br>"
                elif severity == 2:
                    errors_html = CompileErrors.HTML_STYLE_MASK.format(
                        background_color="#CC5500", text_color="#EEEEEE")
                    errors_html += "<b>Warning:</b><br>"
            errors_html += "<div>" + processed_error + "</div>"
        # Add non-breaking space to prevent popup from getting a newline
        # after every word
        return errors_html

    @staticmethod
    def _as_phantom_html(errors_dict):
        """Get error as html for phantom

        Args:
            errors_dict (dict): Current error
        """
        stylesheet = '''
            <style>
                div.error {
                    padding: 0.4rem 0 0.4rem 0.7rem;
                    margin: 0.2rem 0;
                    border-radius: 2px;
                }

                div.error span.message {
                    padding-right: 0.7rem;
                }

                div.error a {
                    text-decoration: inherit;
                    padding: 0.35rem 0.7rem 0.45rem 0.8rem;
                    position: relative;
                    bottom: 0.05rem;
                    border-radius: 0 2px 2px 0;
                    font-weight: bold;
                }
                html.dark div.error a {
                    background-color: #00000018;
                }
                html.light div.error a {
                    background-color: #ffffff18;
                }
            </style>
        '''

        errors_html = '<body id=inline-error>'
        errors_html += stylesheet
        errors_html += '<div class="error">'
        errors_html += '<span class="message">'
        first = True
        for entry in errors_dict:
            processed_error = entry['error']
            processed_error = processed_error.replace(' ', '&nbsp;')
            processed_error = processed_error.replace('<', '&lt;')
            processed_error = processed_error.replace('>', '&gt;')
            if not first:
                processed_error = '<br>' + processed_error
            first = False
            errors_html += processed_error
        errors_html += '</span>'
        errors_html += '<a href=hide>' + chr(0x00D7) + '</a></div>'
        errors_html += '</body>'
        # Add non-breaking space to prevent popup from getting a newline
        # after every word
        return errors_html

    @staticmethod
    def _as_region_list(err_regions_dict):
        """Make a list from error region dict.

        Args:
            err_regions_dict (dict): dict of error regions for current view

        Returns:
            list(Region): list of regions to show on sublime view
        """
        region_list = []
        for errors_list in err_regions_dict.values():
            for error in errors_list:
                region_list.append(error['region'])
        return region_list
