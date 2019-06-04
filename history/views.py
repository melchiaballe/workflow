from itertools import chain
from datetime import datetime, timedelta

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
from rest_framework.generics import ListAPIView

from utils.mixins import Query, TZ, PDFHelper

from .serializers import StandupSerializer, ReportSerializer, ShortStandupProjectSerializer, BlockerSerializer, SearchSerializer
from .models import Blocker, Standup as stand_up_model
from .paginations import WeeklyReportsPagination, ProjectReportsPagination

from accounting.models import Project


class Standups(Query, ViewSet):
    """ daily standups endpoint that receives report
        from our slack workplace (SLACK API)

        *IMPORTANT: Do not ADD authentication on this
            view as it will prevent the standups from
            slack to go through.
    """
    serializer_class = StandupSerializer

    def post(self, *args, **kwargs):
        # this post method is being
        # used by slack api.
        serializer = self.serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=200)

class UserStandups(Query, ListAPIView):
    """ feed endpoint.
        contains scheduled events, daily report, etc.
    """
    queryset = None
    serializer_class = ReportSerializer
    pagination_class = ProjectReportsPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return stand_up_model.objects.filter(user=self.request.user).order_by('-date_created')

class Standup(Query, ViewSet):
    """ daily report endpoint
    """
    serializer_class = ReportSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, *args, **kwargs):
        serializer = self.serializer_class(
            self._get(self._model, **kwargs))

        return Response(serializer.data, status=200)

class StandupByWeek(Query, TZ, ListAPIView):
    """ feed endpoint.
        contains scheduled events, daily report, etc.
    """
    queryset = None
    serializer_class = ShortStandupProjectSerializer
    pagination_class = WeeklyReportsPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # get date parameter from url
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')
        
        start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
        end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))

        #get project id parameter from url
        project_id = self.request.GET.get('project_id')
        # get project object
        project = Project.objects.get(id=project_id)
        queryset = stand_up_model.objects.filter(date_created__range=[start_of_week, end_of_week], project=project).order_by('-date_created')
        return queryset

class ProjectBlockers(Query, ViewSet):
    serializer_class = BlockerSerializer

    def get(self, *args, **kwargs):
        project = Project.objects.get(**kwargs)
        serializer = BlockerSerializer(Blocker.objects.filter(standup__in=project.standup_set.all(), is_fixed=False), many=True)
        return Response(serializer.data, status=200)

class ProjectReport(Query, PDFHelper, ViewSet):

    def get(self, *args, **kwargs):
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')

        start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
        end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))
        project = Project.objects.get(id=kwargs.get('id'))

        queryset = stand_up_model.objects.filter(date_created__range=[start_of_week, end_of_week], project=project).order_by('-date_created')
        serializer = ShortStandupProjectSerializer(queryset, many=True)

        return self.produce_project_report_pdf_as_a_response(serializer.data)

class SearchAll(ListAPIView):

    queryset = None
    serializer_class = SearchSerializer
    pagination_class = WeeklyReportsPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self, *args, **kwargs):
        content = self.request.GET.get('content')
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')
        
        if dt_start:
            start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
            end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))
            instance = sorted(chain(
               Project.objects.filter(name__icontains=content, date_created__range=[start_of_week, end_of_week]).distinct(),
                stand_up_model.objects.filter(Q(date_created__range=[start_of_week, end_of_week]), Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).distinct()
            ),
            key=lambda instance: instance.date_created,
            reverse=True,
        )
        else:
            instance = sorted(chain(
               Project.objects.filter(name__icontains=content).distinct(),
                stand_up_model.objects.filter(Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).distinct()
            ),
            key=lambda instance: instance.date_created,
            reverse=True,
        )

        return instance