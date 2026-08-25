import winUser
import globalPluginHandler
from logHandler import log
from virtualBuffers import gecko_ia2
from comtypes import COMError
from comtypes.hresult import E_INVALIDARG
from comInterfaces import IAccessible2Lib as IA2
import NVDAObjects
def __contains__(self, obj):
	if (
		not (
			isinstance(obj, NVDAObjects.IAccessible.IAccessible)
			and isinstance(obj.IAccessibleObject, IA2.IAccessible2)
		)
		or not obj.windowClassName.startswith("Mozilla")
		or not winUser.isDescendantWindow(self.rootNVDAObject.windowHandle, obj.windowHandle)
	):
		return False
	accId = obj.IA2UniqueID
	if accId == self.rootID:
		return True
	try:
		self.rootNVDAObject.IAccessibleObject.accChild(accId)
	except COMError as e:
		if e.hresult == E_INVALIDARG:
			# This indicates that this id is not a child of this document. We should
			# not treat it as an error.
			return False
		if e.hresult == -2147417842:
			return False
		# This shouldn't happen, so log it. However, don't raise it because we
		# don't want the caller to be impacted. As far as the caller is concerned,
		# this object just isn't in this buffer.
		log.exception("Error checking if obj in buffer")
		return False
	return not self._isNVDAObjectInApplication(obj)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		gecko_ia2.Gecko_ia2.__contains__ = __contains__
