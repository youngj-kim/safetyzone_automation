<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="match_rule_code" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="A_STRONG_OVERLAP" label="A1 강한 직접중첩" symbol="0" render="true"/>
      <category value="A_SHORT_INSIDE" label="A2 짧은 내부포함" symbol="1" render="true"/>
      <category value="A_NEAR_PARALLEL_CORRIDOR" label="A3 근접 평행 보정" symbol="2" render="true"/>
      <category value="A_JUNCTION_COMPONENT" label="A4 교차로/회전교차로 컴포넌트" symbol="3" render="true"/>
      <category value="B_POTENTIAL_GRADE_SEPARATED" label="B 입체도로 의심" symbol="4" render="true"/>
      <category value="B_WEAK_OVERLAP" label="B 약한 중첩" symbol="5" render="true"/>
      <category value="C_NEAR_CONNECTED_OR_SAME_ROAD" label="C 근접 연결/동일도로" symbol="6" render="true"/>
      <category value="D_EXTENDED_NODE_CONNECTED" label="D 확장 연결 검토" symbol="7" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="255,0,0,255"/>
          <prop k="line_width" v="1.20"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="1" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="255,128,0,255"/>
          <prop k="line_width" v="1.20"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="2" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="0,92,230,255"/>
          <prop k="line_width" v="1.20"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="3" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="160,32,240,255"/>
          <prop k="line_width" v="1.20"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="4" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="255,230,0,255"/>
          <prop k="line_width" v="1.10"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dash"/>
        </layer>
      </symbol>
      <symbol name="5" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="140,70,20,255"/>
          <prop k="line_width" v="0.90"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dash"/>
        </layer>
      </symbol>
      <symbol name="6" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="0,180,180,255"/>
          <prop k="line_width" v="0.80"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dot"/>
        </layer>
      </symbol>
      <symbol name="7" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="120,120,120,255"/>
          <prop k="line_width" v="0.70"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dot"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

