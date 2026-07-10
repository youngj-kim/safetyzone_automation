<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="v23_coverage_bucket" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="AUTO_APPLY_READY" label="AUTO_APPLY_READY" symbol="0" render="true"/>
      <category value="POSSIBLE_FALSE_NEGATIVE_REVIEW" label="POSSIBLE_FALSE_NEGATIVE_REVIEW" symbol="1" render="true"/>
      <category value="STRUCTURE_MANUAL_REVIEW" label="STRUCTURE_MANUAL_REVIEW" symbol="2" render="true"/>
      <category value="MANUAL_REVIEW_ONLY" label="MANUAL_REVIEW_ONLY" symbol="3" render="true"/>
      <category value="VALID_NO_STANDARD_LINK_CANDIDATE" label="VALID_NO_STANDARD_LINK_CANDIDATE" symbol="4" render="true"/>
      <category value="VALID_NO_ACCEPTED_CANDIDATE" label="VALID_NO_ACCEPTED_CANDIDATE" symbol="5" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="fill" clip_to_extent="1" alpha="0.35">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="220,20,60,90"/>
            <Option name="outline_color" type="QString" value="220,20,60,255"/>
            <Option name="outline_width" type="QString" value="0.8"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="fill" clip_to_extent="1" alpha="0.45">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="255,0,0,95"/>
            <Option name="outline_color" type="QString" value="255,0,0,255"/>
            <Option name="outline_width" type="QString" value="1.0"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="fill" clip_to_extent="1" alpha="0.35">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="255,215,0,90"/>
            <Option name="outline_color" type="QString" value="255,215,0,255"/>
            <Option name="outline_width" type="QString" value="1.0"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="fill" clip_to_extent="1" alpha="0.35">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="255,140,0,85"/>
            <Option name="outline_color" type="QString" value="255,140,0,255"/>
            <Option name="outline_width" type="QString" value="0.8"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="4" type="fill" clip_to_extent="1" alpha="0.25">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="80,80,80,65"/>
            <Option name="outline_color" type="QString" value="80,80,80,255"/>
            <Option name="outline_width" type="QString" value="0.6"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="5" type="fill" clip_to_extent="1" alpha="0.25">
        <layer enabled="1" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="0,140,255,65"/>
            <Option name="outline_color" type="QString" value="0,140,255,255"/>
            <Option name="outline_width" type="QString" value="0.6"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
