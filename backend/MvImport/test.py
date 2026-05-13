from MvCameraControl_class import *
import cv2
import numpy as np
from ctypes import *


def main():
    # 初始化SDK
    ret = MvCamera.MV_CC_Initialize()
    if ret != 0:
        print(f"SDK初始化失败，错误码: {ret}")
        return

    # 枚举USB设备
    device_list = MV_CC_DEVICE_INFO_LIST()
    ret = MvCamera.MV_CC_EnumDevices(MV_USB_DEVICE, device_list)
    if ret != 0 or device_list.nDeviceNum == 0:
        print("未检测到USB摄像头")
        return

    # 创建相机实例
    cam = MvCamera()
    dev_info = cast(device_list.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    ret = cam.MV_CC_CreateHandle(dev_info)
    if ret != 0:
        print(f"创建句柄失败，错误码: {ret}")
        return

    # 打开设备
    ret = cam.MV_CC_OpenDevice()
    if ret != 0:
        print(f"设备打开失败，错误码: {ret}")
        return

    # 开始采集
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print(f"开始采集失败，错误码: {ret}")
        return

    # 获取单帧图像
    st_frame = MV_FRAME_OUT()
    memset(byref(st_frame), 0, sizeof(st_frame))
    ret = cam.MV_CC_GetImageBuffer(st_frame, 1000)
    if ret == 0:
        # 转换图像格式
        img_data = (c_ubyte * st_frame.stFrameInfo.nFrameLen).from_address(st_frame.pBufAddr)
        img = np.frombuffer(img_data, dtype=np.uint8)
        img = img.reshape((st_frame.stFrameInfo.nHeight, st_frame.stFrameInfo.nWidth, -1))

        # 显示图像
        cv2.imshow('HIKVISION USB Camera', img)
        cv2.waitKey(0)

        # 释放缓冲区
        cam.MV_CC_FreeImageBuffer(st_frame)
    else:
        print(f"获取图像失败，错误码: {ret}")

    # 释放资源
    cam.MV_CC_StopGrabbing()
    cam.MV_CC_CloseDevice()


if __name__ == "__main__":
    main()
