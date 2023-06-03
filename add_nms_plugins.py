import torch 
import torch.nn as nn 
import onnx 
import numpy as np 
import onnx_graphsurgeon as gs 
import argparse


def create_attrs(topK, keepTopK, class_num = 80, scoreThreshold = 0.4, iouThreshold = 0.6):
    attrs = {}
    attrs["shareLocation"] = 1 # Default for yolor
    attrs["backgroundLabelId"] = -1
    attrs["numClasses"] = class_num
    attrs["topK"] = topK
    attrs["keepTopK"] = keepTopK
    attrs["scoreThreshold"] = scoreThreshold
    attrs["iouThreshold"] = iouThreshold
    attrs["isNormalized"] = 0 # Default yolor did not perform normalization
    attrs["clipBoxes"] = 0
    attrs["plugin_version"] = "1"
    return attrs

def create_and_add_plugin_node(graph, topK, keepTopK):
    
    batch_size = graph.inputs[0].shape[0]
    n_boxes = graph.inputs[0].shape[1]

    tensors = graph.tensors()
    boxes_tensor = tensors["bboxes"]
    confs_tensor = tensors["scores"]

    num_detections = gs.Variable(name="num_detections").to_variable(dtype=np.int32, shape=[-1, 1])
    nmsed_boxes = gs.Variable(name="nmsed_boxes").to_variable(dtype=np.float32, shape=[-1, keepTopK, 4])
    nmsed_scores = gs.Variable(name="nmsed_scores").to_variable(dtype=np.float32, shape=[-1, keepTopK])
    nmsed_classes = gs.Variable(name="nmsed_classes").to_variable(dtype=np.float32, shape=[-1, keepTopK])

    new_outputs = [num_detections, nmsed_boxes, nmsed_scores, nmsed_classes]
    print(new_outputs)

    mns_node = gs.Node(
        op="BatchedNMSDynamic_TRT",
        attrs=create_attrs(topK, keepTopK, class_num=80),
        inputs=[boxes_tensor, confs_tensor],
        outputs=new_outputs)

    graph.nodes.append(mns_node)
    graph.outputs = new_outputs

    return graph.cleanup().toposort()

def main():
    parser = argparse.ArgumentParser(description="Add batchedNMSPlugin")
    parser.add_argument("-f", "--model", help="Path to the ONNX model generated by export_model.py", default="yolo.onnx")
    parser.add_argument("-t", "--topK", help="number of bounding boxes for nms", default=2000)
    parser.add_argument("-k", "--keepTopK", help="bounding boxes to be kept per image", default=1000)

    args, _ = parser.parse_known_args()

    graph = gs.import_onnx(onnx.load(args.model))
    
    graph = create_and_add_plugin_node(graph, int(args.topK), int(args.keepTopK))
    
    onnx.save(gs.export_onnx(graph), args.model.replace('.onnx', '') + "-nms.onnx")


if __name__ =="__main__":
    main()