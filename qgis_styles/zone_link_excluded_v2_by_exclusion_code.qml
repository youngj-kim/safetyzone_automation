<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="exclusion_code" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="TINY_ADJACENCY" label="제외: 미세 인접" symbol="0" render="true"/>
      <category value="TOUCH_OR_GRAZE" label="제외: 스침/접촉" symbol="1" render="true"/>
      <category value="NO_AB_SEED" label="제외: A/B seed 없음" symbol="2" render="true"/>
      <category value="EXTENDED_BUT_NOT_NODE_CONNECTED" label="제외: 확장거리이나 노드 연결 부족" symbol="3" render="true"/>
      <category value="NEAR_BUT_UNRELATED_TO_SEED" label="제외: 근접하지만 seed와 무관" symbol="4" render="true"/>
      <category value="V2_RULE_EXCLUDED" label="제외: 기타 v2 규칙 미충족" symbol="5" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="80,80,80,255"/>
          <prop k="line_width" v="0.70"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dash"/>
        </layer>
      </symbol>
      <symbol name="1" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="0,0,0,255"/>
          <prop k="line_width" v="0.70"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dot"/>
        </layer>
      </symbol>
      <symbol name="2" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="180,180,180,255"/>
          <prop k="line_width" v="0.60"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dash"/>
        </layer>
      </symbol>
      <symbol name="3" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="110,110,110,255"/>
          <prop k="line_width" v="0.60"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dash"/>
        </layer>
      </symbol>
      <symbol name="4" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="150,150,150,255"/>
          <prop k="line_width" v="0.60"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dot"/>
        </layer>
      </symbol>
      <symbol name="5" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <prop k="line_color" v="200,200,200,255"/>
          <prop k="line_width" v="0.50"/>
          <prop k="line_width_unit" v="MM"/>
          <prop k="line_style" v="dot"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

