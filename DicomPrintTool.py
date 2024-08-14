import sys
import threading
import time
from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE, evt, debug_logger

BasicGrayscalePrintManagementMeta = '1.2.840.10008.5.1.1.9'
BasicFilmSession = '1.2.840.10008.5.1.1.1'
BasicFilmBox = '1.2.840.10008.5.1.1.2'
BasicGrayscaleImageBox = '1.2.840.10008.5.1.1.4'
Printer = '1.2.840.10008.5.1.1.16'
PrinterInstance = '1.2.840.10008.5.1.1.17'

#Tunable parameters：
AE_Adress = '192.168.88.236'
AE_Port = '104'
DcmPath = 'YourFilm.dcm'    #path of dcm file
setUID = ''   
setBoxUID = ''                  #If these two UID have values, they will be sent continuously using the UID you set; 
                                #If it is empty, call the library to generate it, theoretically it is calculated from the local timestamp, who knows ? :)
                                #reference value 1.2.276.0.7230010.3.1.4.8323328.929.1723453680.299023
setSize = '14INX17IN'   #of cos sizes
sentTime = 3  #(Repeat) Send several tasks
timeSet = 0   #Interval time



debug_logger()

# The SOP Instance containing the grayscale image data to be printed
DATASET = dcmread(DcmPath)


def build_session():
    """Return an N-CREATE *Attribute List* for creating a Basic Film Session

    Returns
    -------
    pydicom.dataset.Dataset
        An N-CREATE *Attribute List* dataset that can be used to create a
        *Basic Film Session SOP Class* instance.
    """
    attr_list = Dataset()
    attr_list.NumberOfCopies = '1'  # IS
    attr_list.PrintPriority = 'LOW'  # CS
    attr_list.MediumType = 'BLUE FILM'  # CS
    attr_list.FilmDestination = 'MAGAZINE'  # CS
    attr_list.FilmSessionLabel = 'TEST JOB'  # LO
    attr_list.MemoryAllocation = ''  # IS
    attr_list.OwnerID = 'DasTest'  # SH

    return attr_list


def build_film_box(sessionInstanceUID):
    """Return an N-CREATE *Attribute List* for creating a Basic Film Box.

    In this example we just have a single Image Box.

    Parameters
    ----------
    session : pydicom.dataset.Dataset
        The *Basic Film Session SOP Class* instance returned by SCP in
        response to the N-CREATE request that created it.

    Returns
    -------
    pydicom.dataset.Dataset
        An N-CREATE *Attribute List* dataset that can be used to create a
        *Basic Film Box SOP Class* instance.
    """
    # The "film" consists of a single Image Box
    attr_list = Dataset()
    attr_list.ImageDisplayFormat = 'STANDARD\\1,1'
    attr_list.FilmOrientation = 'PORTRAIT'
    attr_list.FilmSizeID = setSize

    # Can only contain a single item, is a reference to the *Film Session*
    attr_list.ReferencedFilmSessionSequence = [Dataset()]
    item = attr_list.ReferencedFilmSessionSequence[0]
    item.ReferencedSOPClassUID = BasicFilmSession
    item.ReferencedSOPInstanceUID = sessionInstanceUID

    return attr_list


def build_image_box(im):
    """Return an N-SET *Attribute List* for updating a Basic Grayscale Image Box

    Parameters
    ----------
    im : pydicom.dataset.Dataset
        The SOP Instance containing the pixel data that is to be printed.

    Returns
    -------
    pydicom.dataset.Dataset
        An N-SET *Attribute List* dataset that can be used to update the
        *Basic Grayscale Image Box SOP Class* instance.
    """
    attr_list = Dataset()
    attr_list.ImageBoxPosition = 1  # US

    # Zero or one item only
    attr_list.BasicGrayscaleImageSequence = [Dataset()]
    item = attr_list.BasicGrayscaleImageSequence[0]
    item.SamplesPerPixel = im.SamplesPerPixel
    item.PhotometricInterpretation = im.PhotometricInterpretation
    item.Rows = im.Rows
    item.Columns = im.Columns
    item.BitsAllocated = im.BitsAllocated
    item.BitsStored = im.BitsStored
    item.HighBit = im.HighBit
    item.PixelRepresentation = im.PixelRepresentation
    item.PixelData = im.PixelData

    return attr_list

def handle_n_er(event):
    """Ignore the N-EVENT-REPORT notification"""
    return 0x0000

def setUID_is_empty_string(FKUID):
    if len(FKUID) == 0 or FKUID.isspace():
        return True
    else:
        return False



def send():
    handlers = [(evt.EVT_N_EVENT_REPORT, handle_n_er)]

    ae = AE()
    ae.add_requested_context(BasicGrayscalePrintManagementMeta)
    assoc = ae.associate("192.168.88.236", 104, ae_title=b'PRINTSCP', evt_handlers=handlers)

    if assoc.is_established:
    # Step 1: Check the status of the printer
    # (2110,0010) Printer Status
    # (2110,0020) Printer Status Info
    # Because the association was negotiated using a presentation context
    #   with a Meta SOP Class we need to use the `meta_uid` keyword
    #   parameter to ensure we use the correct context
        status, attr_list = assoc.send_n_get(
            [0x21100010, 0x21100020],  # Attribute Identifier List
            Printer,  # Affected SOP Class UID
            PrinterInstance,  # Well-known Printer SOP Instance
            meta_uid=BasicGrayscalePrintManagementMeta
        )
    # if status and status.Status == 0x0000:
    #     if getattr(attr_list, 'PrinterStatus', None) != "NORMAL":
    #         print(attr_list)
    #         print("Printer status is not 'NORMAL'")
    #         assoc.release()
    #         sys.exit()
    #     else:
    #         print("Failed to get the printer status")
    #         assoc.release()
    #         sys.exit()
    # else:
    #     print("Failed to get the printer status")
    #     assoc.release()
    #     sys.exit()

        print('Printer ready')

    # Step 2: Create *Film Session* instance
        if setUID_is_empty_string(setUID) == False : 
            filmSessionInstanceUID = setUID

        else : 
            filmSessionInstanceUID = generate_uid()
        status, film_session = assoc.send_n_create(
            build_session(),  # Attribute List
            BasicFilmSession,  # Affected SOP Class UID
            filmSessionInstanceUID,  # Affected SOP Instance UID
            meta_uid=BasicGrayscalePrintManagementMeta
        )

    # if not status or status.Status != 0x0000:
    #     print('Creation of Film Session failed, releasing association')
    #     assoc.release()
    #     sys.exit()
        print('Film Session created')

    # Step 3: Create *Film Box* and *Image Box(es)*
        if setUID_is_empty_string(setBoxUID) == False : 
            filmBoxInstanceUID = setBoxUID
           
        else : 
            filmBoxInstanceUID = generate_uid()
        status, film_box = assoc.send_n_create(
            build_film_box(filmSessionInstanceUID),
            BasicFilmBox,
            filmBoxInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )
    # if not status or status.Status != 0x0000:
    #     print('Creation of the Film Box failed, releasing association')
    #     assoc.release()
    #     sys.exit()
        print('Film Box created')

    # Step 4: Update the *Image Box* with the image data
    # In this example we only have one *Image Box* per *Film Box*
    # Get the Image Box's SOP Class and SOP Instance UIDs
        item = film_box.ReferencedImageBoxSequence[0]
        status, image_box = assoc.send_n_set(
            build_image_box(DATASET),
            item.ReferencedSOPClassUID,
            item.ReferencedSOPInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )
    # if not status or status.Status != 0x0000:
    #     print('Updating the Image Box failed, releasing association')
    #     assoc.release()
    #     sys.exit()

        print('Updated the Image Box with the image data')

    # Step 5: Print the *Film Box*
        status, action_reply = assoc.send_n_action(
            None,  # No *Action Information* needed
            1,  # Print the Film Box
            BasicFilmBox,
            filmSessionInstanceUID,
            #filmBoxInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )
    # if not status or status.Status != 0x0000:
    #     print('Printing the Film Box failed, releasing association')
    #     assoc.release()
    #     sys.exit()

    # The actual printing may occur after association release/abort
        print('Print command sent successfully')

    # Optional - Delete the Film Box
        status = assoc.send_n_delete(
            BasicFilmBox,
            filmSessionInstanceUID,
            #filmBoxInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )

    # Optional - Delete the Film Session
        status = assoc.send_n_delete(
            BasicFilmSession,
            filmSessionInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )

    # Release the association
        assoc.release()

i=0


while i<sentTime :
    timer = threading.Timer(timeSet,send())
    timer.start()
    i=i+1
