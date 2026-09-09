"""Optional native macOS CLO control for standalone MCP clients.

Lazy imports keep API-only installations portable. Never opens permissions prompts.
"""
import math
import os
import sys
import time
import uuid


class Desktop:
    def __init__(self):
        self.token = None
        self.nodes = {}
        self.observed_at = 0
        self.observed_pid = None

    def backend(self):
        if sys.platform != 'darwin':
            raise RuntimeError('Desktop control requires macOS')
        try:
            import ApplicationServices as AX
            import Quartz as Q
            import AppKit as AK
        except ImportError as exc:
            raise RuntimeError('Install clo3d-mcp[macos] to enable native desktop tools') from exc
        if not AX.AXIsProcessTrusted():
            raise RuntimeError('Accessibility permission required for the application hosting this MCP server')
        apps = [a for a in AK.NSWorkspace.sharedWorkspace().runningApplications()
                if a.bundleIdentifier() == 'com.clovirtualfashion.CLO_Standalone_OnlineAuth'
                and a.bundleURL().path() == os.environ.get('CLO_APP_PATH', '/Applications/CLO.app')]
        if len(apps) != 1:
            raise RuntimeError('Expected one running CLO app at CLO_APP_PATH (default /Applications/CLO.app)')
        self.AX, self.Q, self.AK, self.app = AX, Q, AK, apps[0]
        self.root = AX.AXUIElementCreateApplication(self.app.processIdentifier())
        AX.AXUIElementSetMessagingTimeout(self.root, 2.0)

    def attr(self, node, name):
        err, value = self.AX.AXUIElementCopyAttributeValue(node, name, None)
        return value if err == 0 else None

    def state(self, max_nodes=1500, max_depth=16):
        if not 1 <= max_nodes <= 5000 or not 1 <= max_depth <= 30:
            raise ValueError('max_nodes 1..5000 and max_depth 1..30 required')
        self.backend()
        self.nodes = {}
        rows, truncated = [], False
        def walk(node, parent, depth):
            nonlocal truncated
            if len(rows) >= max_nodes:
                truncated = True
                return
            index = len(rows)
            row = {'id': index, 'parent': parent}
            self.nodes[index] = node
            for key in ('AXRole', 'AXTitle', 'AXDescription', 'AXValue', 'AXIdentifier', 'AXEnabled'):
                val = self.attr(node, key)
                if val is not None:
                    row[key] = val if isinstance(val, (str, int, float, bool)) else str(val)
            err, actions = self.AX.AXUIElementCopyActionNames(node, None)
            row['actions'] = list(actions or []) if err == 0 else []
            rows.append(row)
            children = list(self.attr(node, 'AXChildren') or [])
            if depth >= max_depth:
                truncated |= bool(children)
            else:
                for child in children:
                    if len(rows) >= max_nodes:
                        truncated = True
                        break
                    walk(child, index, depth+1)
        walk(self.root, None, 0)
        self.token = uuid.uuid4().hex
        self.observed_at = time.monotonic()
        self.observed_pid = self.app.processIdentifier()
        return {'snapshot': self.token, 'pid': self.app.processIdentifier(), 'nodes': rows,
                'truncated': truncated, 'coordinate_system': 'global screen points, origin top-left',
                'windows': self.windows()}

    def windows(self):
        Q = self.Q
        return [{'id': int(w['kCGWindowNumber']), 'name': w.get('kCGWindowName', ''), 'bounds': dict(w['kCGWindowBounds'])}
                for w in Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly, Q.kCGNullWindowID)
                if w.get('kCGWindowOwnerPID') == self.app.processIdentifier() and w.get('kCGWindowLayer') == 0]

    def action(self, snapshot, action, element, value, x, y, end_x, end_y, keycode, modifiers):
        if not self.token or snapshot != self.token or time.monotonic() - self.observed_at > 60:
            raise ValueError('Stale UI snapshot; call clo_ui_state again')
        if action not in {'press','set_value','ax_action','click','right_click','double_click','drag','key','text','scroll'}:
            raise ValueError('Unknown UI action')
        if set(modifiers) - {'command','shift','option','control'}:
            raise ValueError('Unknown modifier')
        if not all(math.isfinite(v) for v in (x,y,end_x,end_y)) or not 0 <= keycode <= 127:
            raise ValueError('Invalid coordinates or keycode')
        self.token = None
        self.backend()
        if self.app.processIdentifier() != self.observed_pid:
            raise ValueError("CLO restarted; inspect UI state again")
        AX, Q = self.AX, self.Q
        self.app.activateWithOptions_(self.AK.NSApplicationActivateIgnoringOtherApps)
        # Fail closed if another application remains focused.
        for _ in range(10):
            if self.AK.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier() == self.app.processIdentifier():
                break
            time.sleep(.02)
        else:
            raise RuntimeError('CLO did not become the frontmost application')
        flags = 0
        for mod in modifiers:
            flags |= getattr(Q, {'command':'kCGEventFlagMaskCommand','shift':'kCGEventFlagMaskShift','option':'kCGEventFlagMaskAlternate','control':'kCGEventFlagMaskControl'}[mod])
        def post(event):
            if event is None:
                raise RuntimeError('Could not create input event')
            Q.CGEventSetFlags(event, flags)
            Q.CGEventPost(Q.kCGHIDEventTap, event)
        if action in {'press','set_value','ax_action'}:
            if element not in self.nodes:
                raise ValueError('Unknown element; inspect UI state first')
            node = self.nodes[element]
            if self.attr(node, 'AXEnabled') is False:
                raise ValueError('Element is disabled')
            if action == 'set_value':
                err = AX.AXUIElementSetAttributeValue(node, 'AXValue', value)
            else:
                chosen = 'AXPress' if action == 'press' else value
                err, available = AX.AXUIElementCopyActionNames(node, None)
                if err or chosen not in (available or []):
                    raise ValueError('Action not exposed by element')
                err = AX.AXUIElementPerformAction(node, chosen)
            if err:
                raise RuntimeError('Accessibility action failed: ' + str(err))
        elif action in {'click','right_click','double_click','drag'}:
            def inside(px, py):
                return any(w['bounds']['X'] <= px < w['bounds']['X'] + w['bounds']['Width'] and w['bounds']['Y'] <= py < w['bounds']['Y'] + w['bounds']['Height'] for w in self.windows())
            if not inside(x,y) or (action == 'drag' and not inside(end_x,end_y)):
                raise ValueError('Pointer coordinates must be inside an observed CLO window')
            right = action == 'right_click'
            button = Q.kCGMouseButtonRight if right else Q.kCGMouseButtonLeft
            down = Q.kCGEventRightMouseDown if right else Q.kCGEventLeftMouseDown
            up = Q.kCGEventRightMouseUp if right else Q.kCGEventLeftMouseUp
            for count in range(1, 3 if action == 'double_click' else 2):
                event = Q.CGEventCreateMouseEvent(None, down, (x,y), button)
                Q.CGEventSetIntegerValueField(event, Q.kCGMouseEventClickState, count)
                post(event)
                try:
                    if action == 'drag':
                        for step in range(1,21):
                            t = step / 20
                            post(Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseDragged, (x+(end_x-x)*t,y+(end_y-y)*t),button))
                            time.sleep(.01)
                finally:
                    event = Q.CGEventCreateMouseEvent(None, up, (end_x,end_y) if action == 'drag' else (x,y),button)
                    Q.CGEventSetIntegerValueField(event, Q.kCGMouseEventClickState, count)
                    post(event)
        elif action in {'key','text'}:
            for down in (True, False):
                event = Q.CGEventCreateKeyboardEvent(None, keycode if action == 'key' else 0, down)
                if action == 'text':
                    Q.CGEventKeyboardSetUnicodeString(event, len(value.encode('utf-16-le'))//2, value)
                post(event)
        else:
            if abs(y) > 100:
                raise ValueError('Scroll delta must be -100..100')
            post(Q.CGEventCreateScrollWheelEvent(None,Q.kCGScrollEventUnitLine,1,int(y)))
        return {'input_delivered': True, 'verification_required': True, 'state': self.state()}

    def screenshot(self):
        self.backend()
        Q = self.Q
        if not Q.CGPreflightScreenCaptureAccess():
            raise RuntimeError('Screen Recording permission required for the MCP host')
        windows = self.windows()
        if not windows:
            raise RuntimeError('No visible CLO window')
        window = windows[0]
        image = Q.CGWindowListCreateImage(Q.CGRectNull, Q.kCGWindowListOptionIncludingWindow, window['id'], Q.kCGWindowImageBoundsIgnoreFraming)
        if image is None:
            raise RuntimeError('CLO window capture failed')
        rep = self.AK.NSBitmapImageRep.alloc().initWithCGImage_(image)
        return bytes(rep.representationUsingType_properties_(self.AK.NSBitmapImageFileTypePNG, {}))
