# Load and dump a CAN database in CDD format.
import logging

from xml.etree import ElementTree

from ..signal import Signal
from ..message import Message
from ..internal_database import InternalDatabase


LOGGER = logging.getLogger(__name__)


class DataType(object):

    def __init__(self,
                 name,
                 id_,
                 bit_length,
                 encoding,
                 minimum,
                 maximum,
                 choices,
                 byte_order,
                 unit,
                 factor,
                 offset):
        self.name = name
        self.id_ = id_
        self.bit_length = bit_length
        self.encoding = encoding
        self.minimum = minimum
        self.maximum = maximum
        self.choices = choices
        self.byte_order = byte_order
        self.unit = unit
        self.factor = factor
        self.offset = offset


def dump_string(database):
    """Format given database in CDD file format.

    """

    raise NotImplementedError('The CDD dump function is not yet implemented.')


def _load_choices(data_type):
    choices = {}

    for choice in data_type.findall('TEXTMAP'):
        start = int(choice.attrib['s'])
        end = int(choice.attrib['e'])

        if start == end:
            choices[start] = choice.find('TEXT/TUV[1]').text

    if not choices:
        choices = None

    return choices


def _load_data_types(ecu_doc):
    """Load all data types found in given ECU doc element.

    """

    data_types = {}

    types = ecu_doc.findall('DATATYPES/IDENT')
    types += ecu_doc.findall('DATATYPES/LINCOMP')
    types += ecu_doc.findall('DATATYPES/TEXTTBL')

    for data_type in types:
        # Default values.
        byte_order = 'big_endian'
        unit = None
        factor = 1
        offset = 0

        # Name and id.
        type_name = data_type.find('NAME/TUV[1]').text
        type_id = data_type.attrib['id']

        # Load from C-type element.
        ctype = data_type.find('CVALUETYPE')

        bit_length = int(ctype.attrib['bl'])
        encoding = ctype.attrib['enc']
        minimum = int(ctype.attrib['minsz'])
        maximum = int(ctype.attrib['maxsz'])

        if ctype.attrib['bo'] == '21':
            byte_order = 'little_endian'

        # Load from P-type element.
        ptype_unit = data_type.find('PVALUETYPE/UNIT')

        if ptype_unit is not None:
            unit = ptype_unit.text

        # Choices, scale and offset.
        choices = _load_choices(data_type)

        # Slope and offset.
        comp = data_type.find('COMP')

        if comp is not None:
            factor = float(comp.attrib['f'])
            offset = float(comp.attrib['o'])

        data_types[type_id] = DataType(type_name,
                                       type_id,
                                       bit_length,
                                       encoding,
                                       minimum,
                                       maximum,
                                       choices,
                                       byte_order,
                                       unit,
                                       factor,
                                       offset)

    return data_types


def _load_signal_element(signal, offset, data_types):
    """Load given signal element and return a signal object.

    """

    data_type = data_types[signal.attrib['dtref']]

    return Signal(name=signal.find('QUAL').text,
                  start=offset,
                  length=data_type.bit_length,
                  receivers=[],
                  byte_order='little_endian',
                  is_signed=False,
                  scale=data_type.factor,
                  offset=data_type.offset,
                  minimum=data_type.minimum,
                  maximum=data_type.maximum,
                  unit=data_type.unit,
                  choices=data_type.choices,
                  comment=None,
                  is_float=False)


def _load_message_element(message, data_types):
    """Load given message element and return a message object.

    """

    offset = 0
    signals = []
    datas = message.findall('SIMPLECOMPCONT/DATAOBJ')
    datas += message.findall('SIMPLECOMPCONT/UNION/STRUCT/DATAOBJ')

    for data_obj in datas:
        signal = _load_signal_element(data_obj,
                                      offset,
                                      data_types)

        if signal:
            signals.append(signal)
            offset += signal.length

    frame_id = int(message.find('STATICVALUE').attrib['v'])
    name = message.find('QUAL').text
    length = (offset + 7) // 8

    return Message(frame_id=frame_id,
                   is_extended_frame=False,
                   name=name,
                   length=length,
                   senders=[],
                   send_type=None,
                   cycle_time=None,
                   signals=signals,
                   comment=None,
                   bus_name=None)


def load_string(string):
    """Parse given CDD format string.

    """

    root = ElementTree.fromstring(string)
    ecu_doc = root.find('ECUDOC')
    data_types = _load_data_types(ecu_doc)
    var = ecu_doc.findall('ECU')[0].find('VAR')
    messages = []

    for diag_class in var.findall('DIAGCLASS'):
        for diag_inst in diag_class.findall('DIAGINST'):
            message = _load_message_element(diag_inst,
                                            data_types)
            messages.append(message)

    return InternalDatabase(messages,
                            [],
                            [],
                            None)
