<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="coverage_status" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="MATCHED_A" label="A 매칭 있음" symbol="0" render="true"/>
      <category value="MATCHED_REVIEW" label="검토 후보만 있음" symbol="1" render="true"/>
      <category value="NO_ACCEPTED_CANDIDATE" label="후보는 있으나 채택 후보 없음" symbol="2" render="true"/>
      <category value="NO_CANDIDATE_WITHIN_20M" label="20m 이내 후보 없음" symbol="3" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="fill" alpha="0.55" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0">
          <prop k="color" v="255,0,0,80"/>
          <prop k="outline_color" v="255,0,0,255"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol name="1" type="fill" alpha="0.55" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0">
          <prop k="color" v="255,200,0,80"/>
          <prop k="outline_color" v="255,160,0,255"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="0.55" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0">
          <prop k="color" v="150,150,150,80"/>
          <prop k="outline_color" v="90,90,90,255"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol name="3" type="fill" alpha="0.55" clip_to_extent="1">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0">
          <prop k="color" v="0,0,0,40"/>
          <prop k="outline_color" v="0,0,0,255"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

