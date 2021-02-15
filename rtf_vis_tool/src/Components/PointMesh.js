import React from "react";

//Unused - Slow Rendering
const PointMesh = (props) => {
    return (
      <mesh position={props.position}>
        <sphereBufferGeometry attach='geometry' args={props.size} />
        <meshStandardMaterial attach='material' color={props.color}/>
      </mesh>
    )
}

export default PointMesh;