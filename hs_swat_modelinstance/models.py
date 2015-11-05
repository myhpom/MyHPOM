__author__ = 'Mohamed Morsy'
from lxml import etree

from django.contrib.contenttypes import generic
from django.db import models
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from mezzanine.pages.page_processors import processor_for

from hs_core.models import BaseResource, ResourceManager, resource_processor, CoreMetaData, AbstractMetaDataElement
from hs_core.hydroshare import utils

from hs_model_program.models import ModelProgramResource

# extended metadata elements for SWAT Model Instance resource type
class ModelOutput(AbstractMetaDataElement):
    term = 'ModelOutput'
    includes_output = models.BooleanField(default=False)

    @property
    def includesModelOutput(self):
        if self.includes_output:
            return "Yes"
        else:
            return "No"

class ExecutedBy(AbstractMetaDataElement):
    term = 'ExecutedBY'
    model_name = models.CharField(max_length=500, choices=(('-', '    '),), default=None)
    model_program_fk = models.ForeignKey('hs_model_program.ModelProgramResource', null=True, blank=True,related_name='swatmodelinstance')

    def __unicode__(self):
        self.model_name

    @property
    def modelProgramName(self):
        if self.model_program_fk:
            return self.model_program_fk.title
        else:
            return "Unspecified"

    @property
    def modelProgramIdentifier(self):
        if self.model_program_fk:
            return '%s%s' % (utils.current_site_url(), self.model_program_fk.get_absolute_url())
        else:
            return "None"

    @classmethod
    def create(cls, **kwargs):
        shortid = kwargs['model_name']
        # get the MP object that matches.  Returns None if nothing is found
        obj = ModelProgramResource.objects.filter(short_id=shortid).first()
        metadata_obj = kwargs['content_object']
        title = obj.title
        return super(ExecutedBy,cls).create(model_program_fk=obj, model_name=title,content_object=metadata_obj)

    @classmethod
    def update(cls, element_id, **kwargs):
        shortid = kwargs['model_name']
        # get the MP object that matches.  Returns None if nothing is found
        obj = ModelProgramResource.objects.filter(short_id=shortid).first()
        return super(ExecutedBy,cls).update(model_program_fk=obj, element_id=element_id)

class ModelObjectiveChoices(models.Model):
    description = models.CharField(max_length=300)

    def __unicode__(self):
        self.description

class ModelObjective(AbstractMetaDataElement):
    term = 'ModelObjective'
    swat_model_objectives = models.ManyToManyField(ModelObjectiveChoices, null=True, blank=True)
    other_objectives = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        self.other_objectives

    def get_swat_model_objectives(self):
        return ', '.join([objective.description for objective in self.swat_model_objectives.all()])

    @classmethod
    def _add_swat_objective(cls,model_objective,objectives):
        for swat_objective in objectives:
            qs = ModelObjectiveChoices.objects.filter(description__iexact=swat_objective)
            if qs.exists():
                model_objective.swat_model_objectives.add(qs[0])
            else:
                model_objective.swat_model_objectives.create(description=swat_objective)

    @classmethod
    def create(cls, **kwargs):
        if 'swat_model_objectives' in kwargs:
            cls._validate_swat_model_objectives(kwargs['swat_model_objectives'])
        else:
            raise ValidationError("swat_model_objectives is missing.")
        model_objective = super(ModelObjective,cls).create(content_object=kwargs['content_object'])
        cls._add_swat_objective(model_objective, kwargs['swat_model_objectives'])

        return model_objective

    @classmethod
    def update(cls, element_id, **kwargs):
        model_objective = ModelObjective.objects.get(id=element_id)
        if model_objective:
            if 'swat_model_objectives' in kwargs:
                cls._validate_swat_model_objectives(kwargs['swat_model_objectives'])
                model_objective.swat_model_objectives.all().delete()
                cls._add_swat_objective(model_objective, kwargs['swat_model_objectives'])

            if 'other_objectives' in kwargs:
                model_objective.other_objectives = kwargs['other_objectives']

            model_objective.save()

            # delete model_objective metadata element if it has no data
            if len(model_objective.swat_model_objectives.all()) == 0 and len(model_objective.other_objectives) == 0:
                model_objective.delete()
        else:
            raise ObjectDoesNotExist("No ModelObjective element was found for the provided id:%s" % kwargs['id'])

    @classmethod
    def _validate_swat_model_objectives(cls, objectives):
        for swat_objective in objectives:
            if swat_objective not in ['Hydrology', 'Water quality', 'BMPs', 'Climate / Landuse Change']:
                raise ValidationError('Invalid swat_model_objectives:%s' % objectives)

class SimulationType(AbstractMetaDataElement):
    term = 'SimulationType'
    type_choices = (('Normal Simulation', 'Normal Simulation'), ('Sensitivity Analysis', 'Sensitivity Analysis'),
                    ('Auto-Calibration', 'Auto-Calibration'))
    simulation_type_name = models.CharField(max_length=100, choices=type_choices, verbose_name='Simulation type')

    def __unicode__(self):
        self.simulation_type_name

class ModelMethod(AbstractMetaDataElement):
    term = 'ModelMethod'
    runoff_calculation_method = models.CharField(max_length=200, null=True, blank=True)
    flow_routing_method = models.CharField(max_length=200, null=True, blank=True)
    PET_estimation_method = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        self.description

    @property
    def runoffCalculationMethod(self):
        return self.runoff_calculation_method

    @property
    def flowRoutingMethod(self):
        return self.flow_routing_method

    @property
    def petEstimationMethod(self):
        return self.PET_estimation_method

    def __unicode__(self):
        self.runoff_calculation_method

class ModelParametersChoices(models.Model):
    description = models.CharField(max_length=300)

    def __unicode__(self):
        self.description

class ModelParameter(AbstractMetaDataElement):
    term = 'ModelParameter'
    model_parameters = models.ManyToManyField(ModelParametersChoices, null=True, blank=True)
    other_parameters = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        self.other_parameters

    def get_swat_model_parameters(self):
        return ', '.join([parameter.description for parameter in self.model_parameters.all()])

    @classmethod
    def _add_swat_parameters(cls,swat_model_parameters,parameters):
        for swat_parameter in parameters:
            qs = ModelParametersChoices.objects.filter(description__iexact=swat_parameter)
            if qs.exists():
                swat_model_parameters.model_parameters.add(qs[0])
            else:
                swat_model_parameters.model_parameters.create(description=swat_parameter)

    @classmethod
    def create(cls, **kwargs):
        if 'model_parameters' in kwargs:
            cls._validate_swat_model_parameters(kwargs['model_parameters'])
        else:
            raise ValidationError("model_parameters is missing.")
        swat_model_parameters = super(ModelParameter,cls).create(content_object=kwargs['content_object'])
        cls._add_swat_parameters(swat_model_parameters,kwargs['model_parameters'])

        return swat_model_parameters

    @classmethod
    def update(cls, element_id, **kwargs):
        swat_model_parameters = ModelParameter.objects.get(id=element_id)
        if swat_model_parameters:
            if 'model_parameters' in kwargs:
                cls._validate_swat_model_parameters(kwargs['model_parameters'])
                swat_model_parameters.model_parameters.all().delete()
                cls._add_swat_parameters(swat_model_parameters,kwargs['model_parameters'])

            if 'other_parameters' in kwargs:
                swat_model_parameters.other_parameters = kwargs['other_parameters']

            swat_model_parameters.save()

            # delete model_parameters metadata element if it has no data
            if len(swat_model_parameters.model_parameters.all()) == 0 and len(swat_model_parameters.other_parameters) == 0:
                swat_model_parameters.delete()
        else:
            raise ObjectDoesNotExist("No ModelParameter element was found for the provided id:%s" % kwargs['id'])

    @classmethod
    def _validate_swat_model_parameters(cls, parameters):
        for swat_parameters in parameters:
            if swat_parameters not in ['Crop rotation', 'Tile drainage', 'Point source', 'Fertilizer', 'Tillage operation', 'Inlet of draining watershed', 'Irrigation operation']:
                raise ValidationError('Invalid swat_model_parameters:%s' % parameters)

class ModelInput(AbstractMetaDataElement):
    term = 'ModelInput'
    rainfall_type_choices = (('Daily', 'Daily'), ('Sub-hourly', 'Sub-hourly'),)
    routing_type_choices = (('Daily', 'Daily'), ('Hourly', 'Hourly'),)
    simulation_type_choices = (('Annual', 'Annual'), ('Monthly', 'Monthly'), ('Daily', 'Daily'), ('Hourly', 'Hourly'),)

    warm_up_period = models.CharField(max_length=100, null=True, blank=True, verbose_name='Warm-up period in years')
    rainfall_time_step_type = models.CharField(max_length=100, choices=rainfall_type_choices, null=True, blank=True)
    rainfall_time_step_value = models.CharField(max_length=100, null=True, blank=True)
    routing_time_step_type = models.CharField(max_length=100, choices=routing_type_choices, null=True, blank=True)
    routing_time_step_value = models.CharField(max_length=100, null=True, blank=True)
    simulation_time_step_type = models.CharField(max_length=100,choices=simulation_type_choices, null=True, blank=True)
    simulation_time_step_value = models.CharField(max_length=100, null=True, blank=True)
    watershed_area = models.CharField(max_length=100, null=True, blank=True, verbose_name='Waterhsed area in square kilometers')
    number_of_subbasins = models.CharField(max_length=100, null=True, blank=True)
    number_of_HRUs = models.CharField(max_length=100, null=True, blank=True)
    DEM_resolution = models.CharField(max_length=100, null=True, blank=True, verbose_name='DEM resolution in meters')
    DEM_source_name = models.CharField(max_length=200, null=True, blank=True)
    DEM_source_URL = models.URLField(null=True, blank=True)
    landUse_data_source_name = models.CharField(max_length=200, null=True, blank=True)
    landUse_data_source_URL = models.URLField(null=True, blank=True)
    soil_data_source_name = models.CharField(max_length=200, null=True, blank=True)
    soil_data_source_URL = models.URLField(null=True, blank=True)

    def __unicode__(self):
        self.rainfall_time_step

    @property
    def warmupPeriodType(self):
        return "Year"

    @property
    def warmupPeriodValue(self):
        return self.warm_up_period

    @property
    def rainfallTimeStepType(self):
        return self.rainfall_time_step_type

    @property
    def rainfallTimeStepValue(self):
        return self.rainfall_time_step_value

    @property
    def routingTimeStepType(self):
        return self.routing_time_step_type

    @property
    def routingTimeStepValue(self):
        return self.routing_time_step_value

    @property
    def simulationTimeStepType(self):
        return self.simulation_time_step_type

    @property
    def simulationTimeStepValue(self):
        return self.simulation_time_step_value

    @property
    def watershedArea(self):
        return self.watershed_area

    @property
    def numberOfSubbasins(self):
        return self.number_of_subbasins

    @property
    def numberOfHRUs(self):
        return self.number_of_HRUs

    @property
    def demResolution(self):
        return self.DEM_resolution

    @property
    def demSourceName(self):
        return self.DEM_source_name

    @property
    def demSourceURL(self):
        return self.DEM_source_URL

    @property
    def landUseDataSourceName(self):
        return self.landUse_data_source_name

    @property
    def landUseDataSourceURL(self):
        return self.landUse_data_source_URL

    @property
    def soilDataSourceName(self):
        return self.soil_data_source_name

    @property
    def soilDataSourceURL(self):
        return self.soil_data_source_URL




#SWAT Model Instance Resource type
class SWATModelInstanceResource(BaseResource):
    objects = ResourceManager("SWATModelInstanceResource")

    class Meta:
        verbose_name = 'SWAT Model Instance Resource'
        proxy = True

    @property
    def metadata(self):
        md = SWATModelInstanceMetaData()
        return self._get_metadata(md)

    @classmethod
    def get_supported_upload_file_types(cls):
        # all file types are supported
        return ('.*')

    @classmethod
    def can_have_multiple_files(cls):
        return True

processor_for(SWATModelInstanceResource)(resource_processor)

# metadata container class
class SWATModelInstanceMetaData(CoreMetaData):
    _model_output = generic.GenericRelation(ModelOutput)
    _executed_by = generic.GenericRelation(ExecutedBy)
    _model_objective = generic.GenericRelation(ModelObjective)
    _simulation_type = generic.GenericRelation(SimulationType)
    _model_method = generic.GenericRelation(ModelMethod)
    _model_parameter = generic.GenericRelation(ModelParameter)
    _model_input = generic.GenericRelation(ModelInput)

    @property
    def model_output(self):
        return self._model_output.all().first()

    @property
    def executed_by(self):
        return self._executed_by.all().first()

    @property
    def model_objective(self):
        return self._model_objective.all().first()

    @property
    def simulation_type(self):
        return self._simulation_type.all().first()

    @property
    def model_method(self):
        return self._model_method.all().first()

    @property
    def model_parameter(self):
        return self._model_parameter.all().first()

    @property
    def model_input(self):
        return self._model_input.all().first()

    @classmethod
    def get_supported_element_names(cls):
        # get the names of all core metadata elements
        elements = super(SWATModelInstanceMetaData, cls).get_supported_element_names()
        # add the name of any additional element to the list
        elements.append('ModelOutput')
        elements.append('ExecutedBy')
        elements.append('ModelObjective')
        elements.append('SimulationType')
        elements.append('ModelMethod')
        elements.append('ModelParameter')
        elements.append('ModelInput')
        return elements

    def has_all_required_elements(self):
        if not super(SWATModelInstanceMetaData, self).has_all_required_elements():
            return False
        if not self.model_objective:
            return False
        return True

    def get_required_missing_elements(self):
        missing_required_elements = super(SWATModelInstanceMetaData, self).get_required_missing_elements()
        if not self.model_objective:
            missing_required_elements.append('ModelObjective')
        return missing_required_elements

    def get_xml(self, pretty_print=True):

        # get the xml string representation of the core metadata elements
        xml_string = super(SWATModelInstanceMetaData, self).get_xml(pretty_print=False)

        # create an etree xml object
        RDF_ROOT = etree.fromstring(xml_string)

        # get root 'Description' element that contains all other elements
        container = RDF_ROOT.find('rdf:Description', namespaces=self.NAMESPACES)

        if self.model_output:
            modelOutputFields = ['includesModelOutput']
            self.add_metadata_element_to_xml(container,self.model_output,modelOutputFields)

        if self.executed_by:
            executedByFields = ['modelProgramName','modelProgramIdentifier']
            self.add_metadata_element_to_xml(container,self.executed_by,executedByFields)
        else:
            hsterms_executed_by = etree.SubElement(container, '{%s}ExecutedBy' % self.NAMESPACES['hsterms'])
            hsterms_executed_by_rdf_Description = etree.SubElement(hsterms_executed_by, '{%s}Description' % self.NAMESPACES['rdf'])
            hsterms_executed_by_name = etree.SubElement(hsterms_executed_by_rdf_Description, '{%s}modelProgramName' % self.NAMESPACES['hsterms'])
            hsterms_executed_by_url = etree.SubElement(hsterms_executed_by_rdf_Description, '{%s}modelProgramIdentifier' % self.NAMESPACES['hsterms'])
            hsterms_executed_by_name.text = "Unspecified"
            hsterms_executed_by_url.text = "None"

        if self.model_objective:
            hsterms_model_objective = etree.SubElement(container, '{%s}modelObjective' % self.NAMESPACES['hsterms'])

            if self.model_objective.other_objectives:
                hsterms_model_objective.text = ', '.join([objective.description for objective in self.model_objective.swat_model_objectives.all()]) + ', ' + self.model_objective.other_objectives
            else:
                hsterms_model_objective.text = ', '.join([objective.description for objective in self.model_objective.swat_model_objectives.all()])

        if self.simulation_type:
            hsterms_simulation_type = etree.SubElement(container, '{%s}simulationType' % self.NAMESPACES['hsterms'])
            hsterms_simulation_type.text = self.simulation_type.simulation_type_name

        if self.model_method:
            modelMethodFields = ['runoffCalculationMethod','flowRoutingMethod','petEstimationMethod']
            self.add_metadata_element_to_xml(container,self.model_method,modelMethodFields)

        if self.model_parameter:
            hsterms_swat_model_parameters = etree.SubElement(container, '{%s}modelParameter' % self.NAMESPACES['hsterms'])

            if self.model_parameter.other_parameters:
                hsterms_swat_model_parameters.text = ', '.join([parameter.description for parameter in self.model_parameter.model_parameters.all()]) + ', ' + self.model_parameter.other_parameters
            else:
                hsterms_swat_model_parameters.text = ', '.join([parameter.description for parameter in self.model_parameter.model_parameters.all()])


        if self.model_input:
            modelInputFields = ['warmupPeriodType','warmupPeriodValue','rainfallTimeStepType','rainfallTimeStepValue','routingTimeStepType',\
                                'routingTimeStepValue','simulationTimeStepType','simulationTimeStepValue','watershedArea','numberOfSubbasins',\
                                'numberOfHRUs','demResolution','demSourceName','demSourceURL','landUseDataSourceName','landUseDataSourceURL',\
                                'soilDataSourceName','soilDataSourceURL']
            self.add_metadata_element_to_xml(container,self.model_input,modelInputFields)

        return etree.tostring(RDF_ROOT, pretty_print=True)

    def delete_all_elements(self):
        super(SWATModelInstanceMetaData, self).delete_all_elements()
        self._model_output.all().delete()
        self._executed_by.all().delete()
        self._model_objective.all().delete()
        self._simulation_type.all().delete()
        self._model_method.all().delete()
        self._model_parameter.all().delete()
        self._model_input.all().delete()

import receivers