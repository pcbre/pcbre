from qtpy import QtCore, QtGui
from copy import copy, deepcopy
from enum import Enum

from pcbre.accel.vert_array import VA_xy
from pcbre.matrix import Point2, Vec2, clip_point_to_rect, Rect
from pcbre.ui.tool_action import MoveEvent
from pcbre.view.rendersettings import RENDER_HINT_ONCE
from pcbre.view.target_const import COL_SEL, COL_SET_MARK, COL_UNSET_MARK

__author__ = 'davidc'

class RenderIcon:
    POINT = 0
    POINT_ON_LINE = 1 # implies has .get_vector()
    LINE = 2 # implies has .get_vector()

class EditablePoint:
    def __init__(self, defv=None, icon=RenderIcon.POINT, enabled=True):
        self.is_set = False
        self.pt = defv
        self.icon = icon

        if not callable(enabled):
            self.__enabled = lambda: enabled
        else:
            self.__enabled = enabled

    @property
    def enabled(self):
        return self.__enabled()

    def save(self):
        return deepcopy((self.is_set, self.pt))

    def restore(self, v):
        self.is_set, self.pt = v

    def set(self, pt):
        self.pt = pt
        self.is_set = True

    def unset(self):
        self.pt = None
        self.is_set = False

    def get(self):
        return self.pt

class OffsetDefaultPoint(EditablePoint):
    def __init__(self, pt, default_offset, icon=RenderIcon.POINT_ON_LINE, enabled=True):
        super(OffsetDefaultPoint, self).__init__(enabled=enabled)
        self.reference = pt
        self.offset = default_offset
        self.icon = icon

    def get_vector(self):
        return self.get() - self.reference.get()


    def get(self):
        if self.is_set:
            return self.pt

        if callable(self.offset):
            offset = self.offset()
        else:
            offset = self.offset

        return self.reference.get() + offset


class DONE_REASON(Enum):
    NOT_DONE = 0
    ACCEPT = 1
    REJECT = 2

def _default_color_fn(flow, pt):
    if pt is flow.current_point:
        return COL_SEL
    elif pt.is_set:
        return COL_SET_MARK
    else:
        return COL_UNSET_MARK


class MultipointEditRenderer:
    def __init__(self, flow, view, color_fn=_default_color_fn, show_fn=lambda pt: pt.enabled):
        """
        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        :param flow:
        :param view:
        :param color_fn:
        :return:
        """
        self.view = view
        self.flow = flow
        self.color_fn = color_fn
        self.show_fn = show_fn

    def render(self):
        N=5

        va_unset = VA_xy(1024)
        va_set= VA_xy(1024)
        va_current = VA_xy(1024)

        corners = list(map(lambda p: Point2(p[0], p[1]), [(-N,-N), (N, -N), (N, N), (-N, N)]))

        for p in self.flow.points:
            if not self.show_fn(p):
                continue

            # TODO
            color = self.color_fn(self.flow, p)
            p_view = self.view.viewState.tfW2V(p.get())
            #p_view = p.get()

            if color == COL_SET_MARK:
                dest = va_set
            elif color == COL_UNSET_MARK:
                dest = va_unset
            elif color == COL_SEL:
                dest = va_current
            else:
                raise NotImplementedError()

            # Draw crappy cross for now

            for pa, pb in zip(corners, corners[1:] + corners[:1]):
                pa_ = p_view + pa
                pb_ = p_view + pb

                dest.add_line(pa_.x, pa_.y, pb_.x, pb_.y)

        self.view.hairline_renderer.render_va(self.view.viewState.glWMatrix,va_current, COL_SEL)
        self.view.hairline_renderer.render_va(self.view.viewState.glWMatrix,va_unset, COL_UNSET_MARK)
        self.view.hairline_renderer.render_va(self.view.viewState.glWMatrix,va_set, COL_SET_MARK)


class MultipointEditFlow:
    def __init__(self, view, points, can_shortcut=False):
        from pcbre.ui.boardviewwidget import BoardViewWidget
        self.view: BoardViewWidget = view
        self.__points = points
        self.__current_point_index = 0
        self.__point_active = False
        self.is_initial_active = True
        self.simple_entry = True
        self.can_shortcut = can_shortcut

        self.__done = DONE_REASON.NOT_DONE

        self.__grab_delta = Vec2(0,0)

    @property
    def current_point(self):
        return self.__points[self.__current_point_index]

    @property
    def points(self):
        return self.__points

    def select_point(self, pt):
        self.__current_point_index = self.__points.index(pt)

    def make_active(self, world_to_point=False):
        self.__saved_point = self.current_point.save()

        if not world_to_point:
            pt = self.view.viewState.tfW2V(self.current_point.get())

            bounds = Rect.from_points(Point2(0, 0), Point2(self.view.width(), self.view.height()))
            pt_clipped = clip_point_to_rect(pt, bounds)

            screen_pt = self.view.mapToGlobal(QtCore.QPoint(*pt_clipped.to_int_tuple()))

            QtGui.QCursor.setPos(screen_pt)
        else:
            rect_qpt = self.view.mapFromGlobal(QtGui.QCursor.pos())
            world_pt = self.view.viewState.tfV2W(Point2(rect_qpt.x(), rect_qpt.y()))
            self.current_point.set(world_pt)

        self.__point_active = True

    def abort_entry(self):
        self.is_initial_active = False

        if self.simple_entry or not self.__point_active:
            self.__done = DONE_REASON.REJECT
        else:
            self.__point_active = False
            self.current_point.restore(self.__saved_point)

    def commit_entry(self, re_edit):
        if self.simple_entry and not re_edit:
            self.__done = DONE_REASON.ACCEPT
            self.__point_active = False
        else:
            self.simple_entry = False
            if self.__point_active:
                self.__point_active = False
                self.next_point()
                if not self.current_point.is_set:
                    if self.is_initial_active:
                        self.__grab_delta = Vec2(0,0)
                        self.make_active()
                else:
                    self.is_initial_active = False
            else:
                self.__done = DONE_REASON.ACCEPT



    def __step_point(self, step):
        for i in range(len(self.points)):
            self.__current_point_index = (self.__current_point_index + step) % len(self.__points)
            if self.current_point.enabled:
                break
        else:
            assert False, "Could not find enabled point"

    def next_point(self):
        self.__step_point(1)

    def prev_point(self):
        self.__step_point(-1)

    def mouse_move(self, evt: MoveEvent):
        if self.__point_active:
            point_pos = self.view.viewState.tfV2W(evt.cursor_pos + self.__grab_delta)
            self.current_point.set(point_pos)
            self.updated(self.current_point)

    def do_jog(self, vec):
        p = self.view.viewState.tfW2V(self.current_point.get())
        self.current_point.set(self.view.viewState.tfV2W(p + vec))
        self.updated(self.current_point)

    def updated(self, ep):
        pass

    def next_option(self):
        pass

    @property
    def done(self):
        return self.__done


