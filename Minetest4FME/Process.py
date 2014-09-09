'''
Created on 08.09.2014

@author: Tino Miegel (t.miegel@conterra.de)
'''
import fmeobjects, zlib, array, cStringIO, fme
import colors

def readU8(f):
    return ord(f.read(1))

def readU16(f):
    return ord(f.read(1)) * 256 + ord(f.read(1))

def readU32(f):
    return ord(f.read(1)) * 256 * 256 * 256 + ord(f.read(1)) * 256 * 256 + ord(f.read(1)) * 256 + ord(f.read(1))

def unsignedToSigned(i, max_positive):
    if i < max_positive:
        return i
    else:
        return i - 2 * max_positive
        
def getIntegerAsBlock(i):
    x = unsignedToSigned(i % 4096, 2048)
    i = int((i - x) / 4096)
    y = unsignedToSigned(i % 4096, 2048)
    i = int((i - y) / 4096)
    z = unsignedToSigned(i % 4096, 2048)
    return x, y, z
    
def readS32(f):
    return unsignedToSigned(ord(f.read(1)) * 256 * 256 * 256 + ord(f.read(1)) * 256 * 256 + ord(f.read(1)) * 256 + ord(f.read(1)), 2 ** 31)
        
def content_is_ignore(d):
    return d in ["ignore"]

def content_is_air(d):
    return d in [126, 127, 254, "air"]

unknown_node_names = []
unknown_node_ids = []

apps = {}

pc = fme.macroValues['pc'] == "Yes"

def buildApps():
    if not pc:
        lib = fmeobjects.FMELibrary()    
        for c in colors.colors.keys():   
            a = fmeobjects.FMEAppearance()
            a.setName(unicode(c))
            a.setColorAmbient(float(colors.colors[c][0]) / 255, float(colors.colors[c][1]) / 255, float(colors.colors[c][2]) / 255)
            key = lib.addAppearance(a)
            apps[c] = key

# Template Class Interface:
class FeatureProcessor(object):
    def __init__(self):
        buildApps()
        pass
    def input(self, feature):
        packer = zlib.decompressobj()
        data = feature.getAttribute("data")
        f = cStringIO.StringIO(data[4:])
        decomp = array.array("B", packer.decompress(f.read()))
        # print(decomp)
        f.close()
        f = cStringIO.StringIO(packer.unused_data)
        # data = packer.unused_data
        packer = zlib.decompressobj()
        meta = array.array("B", packer.decompress(f.read()))
        f.close()
        f = cStringIO.StringIO(packer.unused_data)
        static_object_version = readU8(f)
        static_object_count = readU16(f)
        for i in range(0, static_object_count):
            # u8 type (object type-id)
            object_type = readU8(f)
            # s32 pos_x_nodes * 10000
            pos_x_nodes = readS32(f) / 10000
            # s32 pos_y_nodes * 10000
            pos_y_nodes = readS32(f) / 10000
            # s32 pos_z_nodes * 10000
            pos_z_nodes = readS32(f) / 10000
            # u16 data_size
            data_size = readU16(f)
            # u8[data_size] data
            data = f.read(data_size)
        
        timestamp = readU32(f)
        # print("* timestamp="+str(timestamp))
        
        id_to_name = {}
        name_id_mapping_version = readU8(f)
        num_name_id_mappings = readU16(f)
        # print("* num_name_id_mappings: "+str(num_name_id_mappings))
        for i in range(0, num_name_id_mappings):
            node_id = readU16(f)
            name_len = readU16(f)
            name = f.read(name_len)
            # print(str(node_id)+" = "+name)
            id_to_name[node_id] = name
        # feature.setAttribute("test",id_to_name)
        # feature.setAttribute("timestamp",timestamp)
        # feature.setAttribute("decomp",decomp)
        # feature.setAttribute("version",data[0])
        # feature.setAttribute("flags",data[1])
        # feature.setAttribute("content width",data[2])
        # feature.setAttribute("param width",data[3])
        f.close()
        x, y, z = getIntegerAsBlock(feature.getAttribute("pos"))
        for i in xrange(16):
            for j in xrange(16):
                for k in xrange(16):
                    datapos = i + j * 16 + k * 256
                    content = decomp[datapos * 2] << 8 | decomp[datapos * 2 + 1]
                    try:
                        content = id_to_name[content]
                        #print content 
                    except KeyError:
                        pass
                    if content_is_ignore(content):
                        pass
                    elif content_is_air(content):
                        pass
                    else:
                        f = fmeobjects.FMEFeature()
                        if pc:
                            geom = fmeobjects.FMEPoint(x * 16 + i, y * 16 + j, z * 16 + k)
                            try:
                                #lib = fmeobjects.FMELibrary()
                                #col = lib.getAppearanceCopy(apps[content]).getColorAmbient()
                                #fmeobjects.FMELogFile().logMessageString("color : %i,%i,%i"%(float(col[0])*255,float(col[0])*255,float(col[0])*255), fmeobjects.FME_WARN)
                                f.setAttribute("color_red", "%i"%colors.colors[content][0])
                                f.setAttribute("color_blue", "%i"%colors.colors[content][2])
                                f.setAttribute("color_green", "%i"%colors.colors[content][1])
                            except:
                                fmeobjects.FMELogFile().logMessageString("No color mapping for %s"%content, fmeobjects.FME_WARN)
                        else:
                            geom = fmeobjects.FMEBox((x * 16 + i, y * 16 + j, z * 16 + k, x * 16 + i + 1, y * 16 + j + 1, z * 16 + k + 1))
                            try:
                                geom.setAppearanceReference (apps[content], True)
                            except KeyError:
                                fmeobjects.FMELogFile().logMessageString(content, fmeobjects.FME_WARN)
                        f.setAttribute("content", content)    
                        f.setGeometry(geom)
                        f.setAttribute("pos",feature.getAttribute("pos"))
                        self.pyoutput(f)
                      
                    
        # Check flags
        # is_underground = (data[1] & 1) != 0
        # day_night_differs = (data[1] & 2) != 0
        # lighting_expired = (data[1] & 4) != 0
        # generated = (data[1] & 8) != 0
        # print("is_underground="+str(is_underground))
        # print("day_night_differs="+str(day_night_differs))
        # print("lighting_expired="+str(lighting_expired))
        # print("generated="+str(generated))
        # print("Laenge {}".format(len(data)))
        
    def close(self):
        pass
